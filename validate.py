"""Check the generator against the organisers' reference test vectors.

Usage:
    python validate.py                                   (uses test_vectors/*.txt)
    python validate.py path/to/TC_chain_configurations.txt [more files...]

The file format is the one supplied by the organisers: a block of configurable
parameters, then one or more test cases ("PUS pkt N") listing the expected
TC_Packet, TC_Segment, Transfer_Frame and CLTU bytes in decimal.

Every stage is compared byte by byte, and the first difference is reported.
"""

import glob
import os
import re
import sys
from typing import Dict, List

from cltu.pipeline import GeneratorConfig, INPUT_PUS_DATA, run
from cltu.space_packet import SpacePacketConfig
from cltu.sync_coding import CodingConfig
from cltu.transfer_frame import TransferFrameConfig

HERE = os.path.dirname(os.path.abspath(__file__))

# bypass_contrlcom_flag in the organisers' file: 0 = AD, 2 = BD, 3 = BC (1 is illegal)
FRAME_TYPE_CODES = {0: "AD", 2: "BD", 3: "BC"}

STAGE_KEYS = ["TC_Packet", "TC_Segment", "Transfer_Frame", "CLTU"]


def parse_number(text: str) -> int:
    value = text.strip().replace("_", "")
    if value.isdigit():
        return int(value, 10)
    return int(value, 0)


def parse_parameters(text: str) -> Dict[str, int]:
    """Read lines such as 'int spacecraft_ID= 0b10_0001_0011;' into a dict."""
    params = {}
    pattern = re.compile(r"^\s*(?:byte|int|UInt16|uint|short)\s+(\w+)\s*=\s*([0-9a-fA-FxXbB_]+)\s*;",
                         re.MULTILINE)
    for name, value in pattern.findall(text):
        params[name] = parse_number(value)
    return params


def parse_byte_list(text: str) -> bytes:
    """Read 'new byte[10] { 1, 2, 3 }' into bytes."""
    match = re.search(r"\{([^}]*)\}", text)
    if not match:
        raise ValueError("No byte list found")
    return bytes(parse_number(v) for v in match.group(1).split(",") if v.strip())


def parse_stage_bytes(text: str, key: str) -> bytes:
    """Collect 'KEY [i] : v' and "KEY [i] <= 8'dv;" lines, in index order."""
    pattern = re.compile(r"^\s*" + key + r"\s*\[(\d+)\]\s*(?::|<=)\s*(?:8'd)?(\d+)", re.MULTILINE)
    entries = {int(i): int(v) for i, v in pattern.findall(text)}
    if not entries:
        return b""
    if sorted(entries) != list(range(len(entries))):
        raise ValueError("%s indices are not continuous" % key)
    return bytes(entries[i] for i in range(len(entries)))


def parse_file(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read().replace("\r\n", "\n")

    # Split into the configuration header and the test cases ("////// PUS pkt N //////").
    parts = re.split(r"^/{3,}\s*(PUS pkt[^/]*?)\s*/{3,}\s*$", text, flags=re.MULTILINE)
    header = parts[0]
    defaults = parse_parameters(header)
    default_data = parse_byte_list(header.split("PUS_pkt", 1)[1]) if "PUS_pkt" in header else None

    cases = []
    for name, body in zip(parts[1::2], parts[2::2]):
        params = dict(defaults)
        params.update(parse_parameters(body))
        data = parse_byte_list(body.split("PUS_pkt", 1)[1]) if "PUS_pkt" in body else default_data
        expected = {key: parse_stage_bytes(body, key) for key in STAGE_KEYS}
        cases.append({"name": name.strip(), "params": params, "data": data, "expected": expected})
    return cases


def config_from_params(params: Dict[str, int], data: bytes) -> GeneratorConfig:
    frame_code = params.get("bypass_contrlcom_flag", 2)
    if frame_code not in FRAME_TYPE_CODES:
        raise ValueError("bypass_contrlcom_flag=%d is not a legal frame type" % frame_code)
    sequence_control = params.get("packet_sequence_control", 0xC000)
    return GeneratorConfig(
        input_mode=INPUT_PUS_DATA,
        user_data=data,
        packet=SpacePacketConfig(
            apid=params.get("App_ID", 0),
            version=params.get("version_no", 0),
            secondary_header_flag=params.get("data_header_flg", 1),
            sequence_flags=(sequence_control >> 14) & 0b11,
            sequence_count=sequence_control & 0x3FFF,
            error_control=bool(params.get("error_control_flg", 1)),
        ),
        frame=TransferFrameConfig(
            spacecraft_id=params.get("spacecraft_ID", 0),
            virtual_channel_id=params.get("virtual_channel_ID", 0),
            frame_sequence_number=params.get("frame_sequence_number", 0),
            frame_type=FRAME_TYPE_CODES[frame_code],
            map_id=params.get("MAP_ID", 0),
        ),
        coding=CodingConfig(randomizer=True),
    )


def first_difference(a: bytes, b: bytes) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return "byte %d: expected %02X, got %02X" % (i, x, y)
    return "length: expected %d bytes, got %d" % (len(a), len(b))


def validate_file(path: str) -> bool:
    print("Reference file: %s" % path)
    all_ok = True
    for case in parse_file(path):
        print("\n  Test case: %s" % case["name"])
        result = run(config_from_params(case["params"], case["data"]))
        produced = {
            "TC_Packet": result.packet,
            "TC_Segment": result.stage("Segment").data,
            "Transfer_Frame": result.frame,
            "CLTU": result.cltu,
        }
        for key in STAGE_KEYS:
            expected = case["expected"][key]
            if not expected:
                print("    %-15s (no reference given)" % key)
                continue
            if expected == produced[key]:
                print("    %-15s PASS  (%d bytes)" % (key, len(expected)))
            else:
                all_ok = False
                print("    %-15s FAIL  %s" % (key, first_difference(expected, produced[key])))
    return all_ok


def main(argv: List[str]) -> int:
    paths = argv or sorted(glob.glob(os.path.join(HERE, "test_vectors", "*.txt")))
    if not paths:
        print("No reference files found.")
        return 1
    ok = all([validate_file(p) for p in paths])
    print("\nOVERALL: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
