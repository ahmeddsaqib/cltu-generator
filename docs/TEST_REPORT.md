# Test Report

Date: 8 October 2026. Python 3.11 on Linux. The same commands work on Windows.

## 1. Validation against the organisers' reference vectors

Command: `python validate.py`
Reference file: `test_vectors/TC_chain_configurations.txt` (test case "PUS pkt 1")

Settings from the file: data `01 02 … 0A`, packet version 0, secondary header flag 1, packet sequence control `0xFFFF`, APID 234, packet CRC on, MAP ID 63, frame type BD, SCID 531 (`0b10_0001_0011`), VCID 18, frame sequence number 0.

| Stage | Bytes | Result |
|---|---|---|
| TC_Packet | 18 | **PASS** |
| TC_Segment | 19 | **PASS** |
| Transfer_Frame | 26 | **PASS** |
| CLTU | 42 | **PASS** |

**Overall: PASS.** Every byte of every stage matches.

Generated CLTU:
```
EB 90 DD 2A D6 43 68 16 1E 66 1F 93 76 2F A8 30 5C A4 0B C4 57
AE BC A6 47 5A C8 08 1D 0B F9 6D 81 54 C5 C5 C5 C5 C5 C5 C5 79
```

## 2. Automated tests

Command: `python -m unittest discover -s tests -v`
Result: **37 tests, 37 passed, 0 failed.**

| Group | Test | What it proves | Result |
|---|---|---|---|
| CRC | test_standard_check_value | CRC of "123456789" is 29B1 (published check value) | PASS |
| CRC | test_reference_packet_crc | Packet CRC is CF F0, as in the reference | PASS |
| Randomizer | test_first_40_bits_from_standard | Sequence starts FF 39 9E 5A 68, as printed in CCSDS 231.0 | PASS |
| Randomizer | test_period_is_255_bits | Sequence repeats every 255 bits | PASS |
| Randomizer | test_randomizing_twice_restores_data | De-randomizing gives back the original | PASS |
| BCH | test_codeword_is_divisible_by_generator | Each codeword is an exact multiple of g(x) | PASS |
| BCH | test_all_zero_block | Seven zero bytes give parity byte FE | PASS |
| BCH | test_filler_bit_is_always_zero | The last bit of every parity byte is 0 | PASS |
| BCH | test_every_single_bit_error_is_detected | All 63 single-bit errors are detected | PASS |
| BCH | test_reference_codeblocks | The 4 codeblocks in the reference CLTU are reproduced | PASS |
| Packet | test_reference_packet | Packet matches the reference byte for byte | PASS |
| Packet | test_length_field_leaves_out_the_crc | Length field = data bytes - 1 for 1 to 1000 data bytes | PASS |
| Packet | test_without_crc | Packet without CRC has the correct length | PASS |
| Packet | test_pus_secondary_header | PUS-C secondary header layout | PASS |
| Packet | test_rejects_out_of_range_apid | APID above 2047 is rejected | PASS |
| Frame | test_worked_example_from_guide | Hand-worked header 20 AB 04 13 00 | PASS |
| Frame | test_reference_header | Reference header 22 13 48 19 00 | PASS |
| Frame | test_frame_types | AD, BD and BC flags are correct; AC is rejected | PASS |
| Frame | test_maximum_frame_length | 1024-octet frame accepted, 1025 rejected | PASS |
| Frame | test_no_fecf | Frame without FECF has the correct length field | PASS |
| Frame | test_sequence_number_range | Sequence number 256 is rejected | PASS |
| Coding | test_fill_count | Correct number of fill bytes | PASS |
| Coding | test_cltu_structure | Start sequence, codeblocks and tail sequence in place | PASS |
| Coding | test_fill_is_randomized_with_the_frame | Fill bytes are randomized together with the frame | PASS |
| Coding | test_without_randomizer | Unrandomized CLTU is correct | PASS |
| Physical | test_stream_layout | Acquisition + CLTU + idle | PASS |
| End-to-end | test_organiser_reference_vector | Every reference stage matches | PASS |
| End-to-end | test_decoder_round_trip | Decoding our CLTU gives back the frame (5 sizes, randomizer on and off) | PASS |
| End-to-end | test_random_configurations | 300 random commands and settings (lengths 1-990 bytes, all fill sizes 0-6, all frame/coding options) decode back exactly | PASS |
| End-to-end | test_decoder_catches_corruption | A flipped bit is detected | PASS |
| End-to-end | test_raw_packet_input | Supplying the packet directly gives the same CLTU | PASS |
| End-to-end | test_control_command_frame | A BC frame (Unlock command) is built correctly | PASS |
| End-to-end | test_control_command_format_warning | Unlock / Set V(R) formats from ECSS-E-ST-50-04C 7.8 accepted; anything else flagged | PASS |
| End-to-end | test_ecss_mandatory_options_warn | Switching off FECF or randomizer warns with the ECSS clause | PASS |
| Formatting | test_hex_and_binary | Hex and binary display | PASS |
| Formatting | test_parse_hex | Hex input parsing and error messages | PASS |
| Formatting | test_parse_int | Decimal, hex and binary number input | PASS |

## 3. Performance

Average time for the complete chain (packet to physical stream), over 20 runs each:

| Data bytes | Frame bytes | CLTU bytes | Time | Self-check |
|---|---|---|---|---|
| 10 | 26 | 42 | 0.2 ms | PASS |
| 100 | 116 | 146 | 0.6 ms | PASS |
| 500 | 516 | 602 | 2.4 ms | PASS |
| 999 | 1015 | 1170 | 5.1 ms | PASS |

Even the largest allowed frame is processed in a few milliseconds, which is effectively instant for a user.

## 4. How to reproduce

```
python validate.py
python -m unittest discover -s tests -v
python gui.py      then: Load reference file & validate, and Self-check (decode)
```
