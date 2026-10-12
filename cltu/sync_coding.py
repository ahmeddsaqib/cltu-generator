"""Synchronization and channel coding layer: TC Transfer Frame -> CLTU.

Standard references: CCSDS 231.0-B-4, TC Synchronization and Channel Coding;
ECSS-E-ST-50-04C (31 July 2008) clause 8, the version supplied by the organisers.

  CLTU = Start Sequence (EB 90) + BCH codeblocks + Tail Sequence (C5 C5 C5 C5 C5 C5 C5 79)

Steps:
  1. Fill: pad the frame with 0x55 (alternating 0/1) to a multiple of 7 bytes.
  2. Randomize the frame together with its fill (if enabled).
  3. BCH-encode every 7 bytes into an 8-byte codeblock.
  4. Add the start and tail sequences.

The fill is added first and randomized with the frame, as the organisers' configuration
states ("Filler Bits are added and then whole frame is randomized"). ECSS-E-ST-50-04C
clause 8.4.4 allows this: "The randomization can also be applied to the fill bits added
after the end of the input data to complete the last codeblock of the CLTU". The receiver
discards the fill using the Frame Length field.

Fill pattern: alternating ones and zeros starting with a zero (0x55), ECSS-E-ST-50-04C 8.6.2.
"""

from dataclasses import dataclass, field
from typing import List

from . import bch
from .randomizer import randomize

START_SEQUENCE = bytes([0xEB, 0x90])
TAIL_SEQUENCE = bytes([0xC5] * 7 + [0x79])
FILL_BYTE = 0x55


@dataclass
class CodingConfig:
    randomizer: bool = True


@dataclass
class CodingResult:
    filled: bytes            # frame + fill bytes
    randomized: bytes        # data entering the BCH encoder
    codeblocks: List[bytes] = field(default_factory=list)
    cltu: bytes = b""


def fill_count(length: int) -> int:
    """Number of fill bytes needed to reach a multiple of 7."""
    return (-length) % bch.INFO_BYTES


def build_cltu(frame: bytes, cfg: CodingConfig) -> CodingResult:
    fill = bytes([FILL_BYTE] * fill_count(len(frame)))
    filled = frame + fill

    coder_input = randomize(filled) if cfg.randomizer else filled

    coded = bch.encode(coder_input)
    blocks = [coded[i:i + bch.CODEBLOCK_BYTES] for i in range(0, len(coded), bch.CODEBLOCK_BYTES)]
    cltu = START_SEQUENCE + coded + TAIL_SEQUENCE
    return CodingResult(filled=filled, randomized=coder_input, codeblocks=blocks, cltu=cltu)
