"""Automated tests for every stage of the chain.

Run from the cltu-generator folder:
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cltu import bch                                              # noqa: E402
from cltu.crc import crc16                                        # noqa: E402
from cltu.decoder import decode_cltu                              # noqa: E402
from cltu.formatting import parse_hex, parse_int, to_binary, to_hex  # noqa: E402
from cltu.physical import PhysicalConfig, build_physical_stream   # noqa: E402
from cltu.pipeline import (GeneratorConfig, INPUT_CONTROL_COMMAND,  # noqa: E402
                           INPUT_RAW_PACKET, run)
from cltu.randomizer import randomize, random_sequence            # noqa: E402
from cltu.space_packet import (PusSecondaryHeader,  # noqa: E402
                               SpacePacketConfig, build_space_packet)
from cltu.sync_coding import (CodingConfig,  # noqa: E402
                              START_SEQUENCE, TAIL_SEQUENCE, build_cltu, fill_count)
from cltu.transfer_frame import (TransferFrameConfig, build_primary_header,  # noqa: E402
                                 build_transfer_frame)
import validate                                                   # noqa: E402

GENERATOR_POLY = 0b11000101   # x^7 + x^6 + x^2 + 1


def poly_mod(value: int, value_bits: int) -> int:
    """Remainder of a binary polynomial divided by the BCH generator (long division)."""
    for shift in range(value_bits - 1, 6, -1):
        if value & (1 << shift):
            value ^= GENERATOR_POLY << (shift - 7)
    return value


class CrcTests(unittest.TestCase):
    def test_standard_check_value(self):
        # Published check value of CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)
        self.assertEqual(crc16(b"123456789"), 0x29B1)

    def test_reference_packet_crc(self):
        header_and_data = bytes([0x18, 0xEA, 0xFF, 0xFF, 0x00, 0x09]) + bytes(range(1, 11))
        self.assertEqual(crc16(header_and_data), 0xCFF0)


class RandomizerTests(unittest.TestCase):
    def test_first_40_bits_from_standard(self):
        self.assertEqual(random_sequence(5), bytes.fromhex("FF399E5A68"))

    def test_period_is_255_bits(self):
        bits = "".join("{:08b}".format(b) for b in random_sequence(64))
        self.assertEqual(bits[:255], bits[255:510])
        self.assertNotEqual(bits[:100], bits[1:101])

    def test_randomizing_twice_restores_data(self):
        data = bytes(range(200))
        self.assertEqual(randomize(randomize(data)), data)


class BchTests(unittest.TestCase):
    def test_codeword_is_divisible_by_generator(self):
        for info in [bytes(7), bytes([0xFF] * 7), bytes(range(1, 8)), bytes.fromhex("DD2AD64368161E")]:
            parity = bch.parity_bits(info)
            codeword = (int.from_bytes(info, "big") << 7) | parity
            self.assertEqual(poly_mod(codeword, 63), 0, info.hex())

    def test_all_zero_block(self):
        # Parity of zeros is 0, complemented = 1111111, plus filler bit 0 = 0xFE
        self.assertEqual(bch.encode_codeblock(bytes(7))[-1], 0xFE)

    def test_filler_bit_is_always_zero(self):
        for n in range(256):
            info = bytes([n] * 7)
            self.assertEqual(bch.parity_byte(info)[0] & 1, 0)

    def test_every_single_bit_error_is_detected(self):
        info = bytes.fromhex("0102030405060708")[:7]
        good = (int.from_bytes(info, "big") << 7) | bch.parity_bits(info)
        for bit in range(63):
            self.assertNotEqual(poly_mod(good ^ (1 << bit), 63), 0)

    def test_reference_codeblocks(self):
        # The four codeblocks inside the organisers' reference CLTU
        blocks = ["DD2AD64368161E66", "1F93762FA8305CA4", "0BC457AEBCA6475A", "C8081D0BF96D8154"]
        for block in blocks:
            raw = bytes.fromhex(block)
            self.assertEqual(bch.encode_codeblock(raw[:7]), raw, block)


class PacketTests(unittest.TestCase):
    def test_reference_packet(self):
        cfg = SpacePacketConfig(apid=234, sequence_flags=3, sequence_count=0x3FFF)
        packet = build_space_packet(bytes(range(1, 11)), cfg)
        self.assertEqual(packet.hex().upper(), "18EAFFFF00090102030405060708090ACFF0")

    def test_length_field_leaves_out_the_crc(self):
        """Length field = data bytes - 1 for every data length; the 2 CRC bytes are not counted."""
        for n in (1, 2, 10, 100, 1000):
            packet = build_space_packet(bytes(n), SpacePacketConfig())
            self.assertEqual(int.from_bytes(packet[4:6], "big"), n - 1)
            self.assertEqual(len(packet), 6 + n + 2)

    def test_without_crc(self):
        cfg = SpacePacketConfig(error_control=False)
        packet = build_space_packet(b"\x01\x02", cfg)
        self.assertEqual(len(packet), 8)
        self.assertEqual(int.from_bytes(packet[4:6], "big"), 1)

    def test_pus_secondary_header(self):
        header = PusSecondaryHeader(pus_version=2, ack_flags=0b1001, service_type=17,
                                    service_subtype=1, source_id=5, source_id_bytes=2)
        self.assertEqual(header.to_bytes(), bytes([0x29, 17, 1, 0x00, 0x05]))

    def test_rejects_out_of_range_apid(self):
        with self.assertRaises(ValueError):
            build_space_packet(b"\x01", SpacePacketConfig(apid=2048))


class TransferFrameTests(unittest.TestCase):
    def test_worked_example_from_guide(self):
        cfg = TransferFrameConfig(spacecraft_id=171, virtual_channel_id=1,
                                  frame_sequence_number=0, frame_type="BD")
        self.assertEqual(build_primary_header(cfg, 20).hex().upper(), "20AB041300")

    def test_reference_header(self):
        cfg = TransferFrameConfig()
        self.assertEqual(build_primary_header(cfg, 26).hex().upper(), "2213481900")

    def test_frame_types(self):
        for frame_type, first_byte in (("AD", 0x02), ("BD", 0x22), ("BC", 0x32)):
            cfg = TransferFrameConfig(frame_type=frame_type)
            self.assertEqual(build_primary_header(cfg, 10)[0], first_byte)
        with self.assertRaises(ValueError):
            build_primary_header(TransferFrameConfig(frame_type="AC"), 10)

    def test_maximum_frame_length(self):
        cfg = TransferFrameConfig(use_fecf=True)
        self.assertEqual(len(build_transfer_frame(bytes(1017), cfg)), 1024)
        with self.assertRaises(ValueError):
            build_transfer_frame(bytes(1018), cfg)

    def test_no_fecf(self):
        frame = build_transfer_frame(b"\xAA", TransferFrameConfig(use_fecf=False))
        self.assertEqual(len(frame), 6)
        self.assertEqual(((frame[2] & 3) << 8 | frame[3]) + 1, 6)

    def test_sequence_number_range(self):
        with self.assertRaises(ValueError):
            build_primary_header(TransferFrameConfig(frame_sequence_number=256), 10)


class CodingTests(unittest.TestCase):
    def test_fill_count(self):
        self.assertEqual([fill_count(n) for n in (7, 8, 13, 14, 26)], [0, 6, 1, 0, 2])

    def test_cltu_structure(self):
        result = build_cltu(bytes(range(26)), CodingConfig())
        self.assertTrue(result.cltu.startswith(START_SEQUENCE))
        self.assertTrue(result.cltu.endswith(TAIL_SEQUENCE))
        self.assertEqual(len(result.cltu), 2 + 4 * 8 + 8)

    def test_fill_is_randomized_with_the_frame(self):
        frame = bytes(range(26))
        coded = build_cltu(frame, CodingConfig()).randomized
        sequence = random_sequence(28)
        self.assertEqual(coded[:26], randomize(frame))
        self.assertEqual(coded[26:], bytes(0x55 ^ r for r in sequence[26:]))

    def test_without_randomizer(self):
        result = build_cltu(bytes(7), CodingConfig(randomizer=False))
        self.assertEqual(result.cltu, START_SEQUENCE + bytes(7) + b"\xFE" + TAIL_SEQUENCE)


class PhysicalTests(unittest.TestCase):
    def test_stream_layout(self):
        stream = build_physical_stream(b"\xEB\x90", PhysicalConfig(acquisition_octets=16, idle_octets=2))
        self.assertEqual(stream, b"\x55" * 16 + b"\xEB\x90" + b"\x55" * 2)


class EndToEndTests(unittest.TestCase):
    def test_organiser_reference_vector(self):
        path = os.path.join(ROOT, "test_vectors", "TC_chain_configurations.txt")
        cases = validate.parse_file(path)
        self.assertTrue(cases)
        for case in cases:
            result = run(validate.config_from_params(case["params"], case["data"]))
            self.assertEqual(result.packet, case["expected"]["TC_Packet"])
            self.assertEqual(result.stage("Segment").data, case["expected"]["TC_Segment"])
            self.assertEqual(result.frame, case["expected"]["Transfer_Frame"])
            self.assertEqual(result.cltu, case["expected"]["CLTU"])

    def test_decoder_round_trip(self):
        for randomizer in (True, False):
            for length in (1, 6, 7, 20, 300):
                cfg = GeneratorConfig(user_data=bytes(i % 256 for i in range(length)))
                cfg.coding.randomizer = randomizer
                result = run(cfg)
                report = decode_cltu(result.cltu, randomizer=randomizer)
                self.assertTrue(report.ok, report.messages)
                self.assertEqual(report.frame, result.frame)

    def test_random_configurations(self):
        """300 random commands and settings: every CLTU decodes back to its frame,
        and the header fields read back exactly as they were set."""
        import random
        rng = random.Random(2026)
        fills = set()
        for _ in range(300):
            cfg = GeneratorConfig(user_data=bytes(rng.randrange(256) for _ in range(rng.randint(1, 990))))
            cfg.packet = SpacePacketConfig(apid=rng.randrange(2048), sequence_flags=rng.randrange(4),
                                           sequence_count=rng.randrange(16384),
                                           error_control=rng.random() < 0.5)
            cfg.frame = TransferFrameConfig(spacecraft_id=rng.randrange(1024),
                                            virtual_channel_id=rng.randrange(64),
                                            frame_sequence_number=rng.randrange(256),
                                            frame_type=rng.choice(["AD", "BD"]),
                                            map_id=rng.randrange(64), use_fecf=rng.random() < 0.7)
            cfg.coding = CodingConfig(randomizer=rng.random() < 0.8)
            result = run(cfg)
            report = decode_cltu(result.cltu, randomizer=cfg.coding.randomizer,
                                 has_fecf=cfg.frame.use_fecf)
            self.assertTrue(report.ok, report.messages)
            self.assertEqual(report.frame, result.frame)
            f, p = result.frame, result.packet
            self.assertEqual((f[0] & 3) << 8 | f[1], cfg.frame.spacecraft_id)
            self.assertEqual(f[2] >> 2, cfg.frame.virtual_channel_id)
            self.assertEqual(f[4], cfg.frame.frame_sequence_number)
            self.assertEqual((p[0] & 7) << 8 | p[1], cfg.packet.apid)
            fills.add(len(result.stage("Frame + fill").data) - len(f))
        self.assertEqual(fills, set(range(7)))   # every possible fill size was exercised

    def test_decoder_catches_corruption(self):
        result = run(GeneratorConfig())
        damaged = bytearray(result.cltu)
        damaged[5] ^= 0x10
        self.assertFalse(decode_cltu(bytes(damaged)).ok)

    def test_raw_packet_input(self):
        packet = bytes.fromhex("18EAFFFF00090102030405060708090ACFF0")
        result = run(GeneratorConfig(input_mode=INPUT_RAW_PACKET, user_data=packet))
        self.assertEqual(result.cltu, run(GeneratorConfig()).cltu)

    def test_control_command_format_warning(self):
        cfg = GeneratorConfig(input_mode=INPUT_CONTROL_COMMAND, user_data=bytes([0x82, 0x00, 0x05]))
        cfg.frame.frame_type = "BC"
        self.assertEqual(run(cfg).warnings, [])           # Set V(R) = 5 is valid
        cfg.user_data = b"\x01"
        self.assertTrue(any("COP-1" in w for w in run(cfg).warnings))

    def test_ecss_mandatory_options_warn(self):
        cfg = GeneratorConfig()
        cfg.frame.use_fecf = False
        cfg.coding.randomizer = False
        text = " ".join(run(cfg).warnings)
        self.assertIn("6.2.4", text)
        self.assertIn("8.4.2", text)

    def test_control_command_frame(self):
        cfg = GeneratorConfig(input_mode=INPUT_CONTROL_COMMAND, user_data=b"\x00")  # Unlock
        cfg.frame.frame_type = "BC"
        result = run(cfg)
        self.assertEqual(result.frame[0] & 0x30, 0x30)
        self.assertEqual(len(result.frame), 5 + 1 + 2)


class FormattingTests(unittest.TestCase):
    def test_hex_and_binary(self):
        self.assertEqual(to_hex(b"\xEB\x90"), "EB 90")
        self.assertEqual(to_binary(b"\xEB\x90"), "11101011 10010000")

    def test_parse_hex(self):
        self.assertEqual(parse_hex("0x01, 0x0a 0B"), b"\x01\x0A\x0B")
        with self.assertRaises(ValueError):
            parse_hex("123")
        with self.assertRaises(ValueError):
            parse_hex("GG")

    def test_parse_int(self):
        self.assertEqual(parse_int("0b10_0001_0011"), 531)
        self.assertEqual(parse_int("0x213"), 531)
        self.assertEqual(parse_int("018"), 18)


if __name__ == "__main__":
    unittest.main()
