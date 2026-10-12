"""A simple receiver-side check: take a CLTU apart again and confirm every layer.

This is not needed to generate CLTUs. It exists so the team can show the jury that
the output is self-consistent: every BCH codeblock checks out, de-randomizing gives
back the frame, and both CRCs are correct.
"""

from dataclasses import dataclass
from typing import List

from . import bch
from .crc import crc16
from .randomizer import derandomize
from .sync_coding import START_SEQUENCE, TAIL_SEQUENCE


@dataclass
class DecodeReport:
    frame: bytes
    codeblocks_ok: List[bool]
    fecf_ok: bool
    messages: List[str]

    @property
    def ok(self) -> bool:
        return all(self.codeblocks_ok) and self.fecf_ok


def decode_cltu(cltu: bytes, randomizer: bool = True, has_fecf: bool = True) -> DecodeReport:
    messages = []
    if not cltu.startswith(START_SEQUENCE):
        raise ValueError("CLTU does not begin with the start sequence EB 90")
    if not cltu.endswith(TAIL_SEQUENCE):
        raise ValueError("CLTU does not end with the tail sequence")
    body = cltu[len(START_SEQUENCE):-len(TAIL_SEQUENCE)]
    if len(body) % bch.CODEBLOCK_BYTES:
        raise ValueError("CLTU body is not a whole number of 8-byte codeblocks")

    info = bytearray()
    checks = []
    for i in range(0, len(body), bch.CODEBLOCK_BYTES):
        block = body[i:i + bch.CODEBLOCK_BYTES]
        good = bch.parity_byte(block[:7]) == block[7:]
        checks.append(good)
        if not good:
            messages.append("Codeblock %d fails the BCH check" % (i // 8))
        info += block[:7]

    if randomizer:
        # The pseudo-random sequence restarts at the first byte of the frame, so
        # de-randomizing everything gives the frame back. Bytes after the frame
        # (the fill) are discarded below either way.
        info = bytearray(derandomize(bytes(info)))
    # Frame length is in header bits 22-31 and holds (total octets - 1)
    frame_length = (((info[2] & 0x03) << 8) | info[3]) + 1
    if frame_length > len(info):
        raise ValueError("Frame length field is larger than the decoded data")
    frame = bytes(info[:frame_length])

    fecf_ok = True
    if has_fecf:
        fecf_ok = crc16(frame[:-2]) == int.from_bytes(frame[-2:], "big")
        if not fecf_ok:
            messages.append("Frame Error Control Field does not match")
    return DecodeReport(frame=frame, codeblocks_ok=checks, fecf_ok=fecf_ok, messages=messages)
