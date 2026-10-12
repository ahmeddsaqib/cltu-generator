# Compliance Matrix

This table links each requirement of the challenge and each rule of the CCSDS and ECSS standards to the code that implements it and the test that proves it.

Standards used:
- **[SPP]** CCSDS 133.0-B-2, Space Packet Protocol
- **[PUS]** ECSS-E-ST-70-41C, Telemetry and telecommand packet utilization
- **[SDLP]** CCSDS 232.0-B-4, TC Space Data Link Protocol
- **[SCC]** CCSDS 231.0-B-4, TC Synchronization and Channel Coding
- **[E50]** ECSS-E-ST-50-04C (31 July 2008), *Space data links: Telecommand protocols, synchronization and channel coding*. This is the standard supplied by the hackathon focal person. It is the ECSS version of [SDLP] and [SCC], and it makes some CCSDS options mandatory (see section 3).

Test names refer to `tests/test_chain.py`. "Reference" means the organisers' file `test_vectors/TC_chain_configurations.txt`, checked by `validate.py`.

## 1. Challenge requirements

| # | Requirement (from the challenge) | Where | Evidence |
|---|---|---|---|
| R1 | Standalone, user-friendly application | `gui.py`, Python standard library only | Runs offline; no installs beyond Python |
| R2 | Accept a PUS telecommand / Space Packet as input | GUI "Input type": PUS data field, complete Space Packet, or control command | `test_raw_packet_input`, `test_control_command_frame` |
| R3 | Configure SCID, VCID, sequence number, bypass flag, control command flag and other frame parameters | GUI section 2 | `test_frame_types`, `test_reference_header` |
| R4 | Build the TC Transfer Frame per CCSDS | `transfer_frame.py` | Reference `Transfer_Frame` PASS |
| R5 | Primary header, data field, segment header, FECF | `build_primary_header`, `build_segment`, `build_transfer_frame` | Reference `TC_Segment` and `Transfer_Frame` PASS |
| R6 | Process the frame per TC Synchronization and Channel Coding | `sync_coding.py` | Reference `CLTU` PASS |
| R7 | BCH channel coding | `bch.py` | `BchTests` (5 tests) |
| R8 | Randomization / de-randomization | `randomizer.py` (`randomize`, `derandomize`) | `RandomizerTests` (3 tests) |
| R9 | CLTU with start sequence, coded data, tail sequence | `build_cltu` | `test_cltu_structure`, reference `CLTU` PASS |
| R10 | Inspect intermediate outputs: packet, frame, FECF/CRC, coded data, randomized data, CLTU | `pipeline.run` records each stage; GUI "Every intermediate stage" box | Visible in the GUI and in the saved report |
| R11 | Hex and binary for each stage | `formatting.to_hex`, `to_binary`; GUI Hex/Binary switch | `test_hex_and_binary` |
| R12 | Export the CLTU as binary and hex files | GUI "Save CLTU (.bin)" and "Save CLTU (.hex)" | |
| R13 | Open-source software | Python 3 (PSF licence), standard library only | |
| R14 | Documentation of compliance | This file, `HOW_IT_WORKS.md`, `TEST_REPORT.md` | |
| R15 | Three layers: transfer, sync & coding, physical (focal person) | `transfer_frame.py`, `sync_coding.py`, `physical.py` | `test_stream_layout` |
| R16 | Segment header hard-coded (focal person) | `SEGMENT_SEQUENCE_FLAGS = 0b11` | Reference `TC_Segment` PASS |
| R17 | Each layer's output in its own hex text field (focal person) | GUI: three layer boxes | |
| R18 | Validation against the provided test vectors | `validate.py`, GUI "Load reference file & validate" | 4 of 4 stages PASS |

## 2. Standard rules

| Rule | Standard | Implementation | Test |
|---|---|---|---|
| Packet version `000`, type 1 for TC, secondary header flag, 11-bit APID | [SPP] | `build_space_packet` | `test_reference_packet` |
| Sequence flags (2 bits) + sequence count (14 bits) | [SPP] | `build_space_packet` | `test_reference_packet` |
| Packet Data Length = data octets − 1, CRC not counted (focal person's instruction; differs from [SPP], see note 1) | Focal person | `build_space_packet` | `test_length_field_leaves_out_the_crc`, reference vector PASS |
| PUS TC secondary header (version, ack flags, service, subtype, source ID) | [PUS] | `PusSecondaryHeader` | `test_pus_secondary_header` |
| Packet Error Control, CRC-16 | [PUS] | `crc16_bytes` | `test_reference_packet_crc` |
| Frame version `00`, bypass, control command, spare `00` | [SDLP] | `build_primary_header` | `test_frame_types` |
| Bypass 0 + control 1 not allowed | [SDLP] | `FRAME_TYPES` lookup | `test_frame_types` |
| SCID 10 bits, VCID 6 bits, frame sequence number 8 bits | [SDLP] | `build_primary_header` | `test_sequence_number_range`, `test_worked_example_from_guide` |
| Frame Length = total octets − 1; frames 8 to 1024 octets | [SDLP], [E50] 6.2.2.8 | `build_transfer_frame` | `test_maximum_frame_length`, `test_no_fecf` |
| Segment header always present in a TC Segment: sequence flags (2 bits) + MAP ID (6 bits) | [SDLP], [E50] 5.2.2 | `build_segment` | reference |
| Type-C frames carry a COP-1 control command in the data field | [SDLP], [E50] 6.2.3 | `pipeline.run` | `test_control_command_frame` |
| FECF: CRC-16, G(X) = X¹⁶+X¹²+X⁵+1, register preset to all ones; always present in [E50] | [SDLP], [E50] 6.2.4 | `crc.py` | `test_standard_check_value` |
| Randomizer h(x) = x⁸+x⁶+x⁴+x³+x²+x+1, all-ones start, first 40 bits `FF399E5A68` | [SCC], [E50] 8.4.3 | `random_sequence` | `test_first_40_bits_from_standard`, `test_period_is_255_bits` |
| Randomization of each codeblock's data before BCH encoding; mandatory in [E50] | [SCC], [E50] 8.4.2 | `build_cltu` | reference |
| BCH(63,56), g(x) = x⁷+x⁶+x²+1, complemented parity, filler bit 0 | [SCC], [E50] 8.2.3, 8.5 | `bch.py` | `test_codeword_is_divisible_by_generator`, `test_filler_bit_is_always_zero`, `test_all_zero_block` |
| Fill: whole octets, last codeblock only, alternating bits starting with a zero (`55`) | [SCC], [E50] 8.6.2 | `FILL_BYTE` | `test_fill_count` |
| Start sequence `EB90` | [SCC], [E50] 8.3.2 | `START_SEQUENCE` | `test_cltu_structure` |
| Tail sequence `C5C5C5C5C5C5C579` | [SCC], [E50] 8.3.4 | `TAIL_SEQUENCE` | `test_cltu_structure` |
| Acquisition sequence of alternating bits, at least 128 bits (16 octets) | [SCC] PLOP, [E50] 9.2.1 | `physical.py` (warning if shorter) | `test_stream_layout` |
| Idle sequence of alternating bits, at least 8 bits | [SCC] PLOP, [E50] 9.2.3 | `physical.py` (warning if shorter) | `test_stream_layout` |

## 3. Notes on the organisers' reference

**Note 1: Packet Data Length.** This field belongs to the Space Packet, which [E50] does not define (its clause 5 only refers to "packet length fields"). [SPP] section 4.1.3.5 defines the field as "a length count C that equals one fewer than the length (in octets) of the Packet Data Field", i.e. C = (total octets in the Packet Data Field) - 1, and the Packet Data Field includes the Packet Error Control. For the reference packet (10 data octets + 2 CRC octets) that gives 11. The organisers' reference contains 9. The hackathon focal person confirmed on 8 October 2026 that, for this challenge, the field must exclude the packet CRC: "The length field in header will contain data field length - 1". The program follows the focal person's instruction: length field = data bytes - 1, giving 9, which matches the test vector.

**Note 2: Fill and randomization.** The organisers' configuration file states that "Filler Bits are added and then whole frame is randomized", and the program does exactly that, which reproduces their reference CLTU. [E50] clause 8.4.4 permits it: "The randomization can also be applied to the fill bits added after the end of the input data to complete the last codeblock of the CLTU". The receiver discards the fill using the Frame Length field.

**Note 3: Options that ECSS makes mandatory.** CCSDS leaves the FECF and the randomizer optional. [E50] requires both: "The Frame Error Control Field shall always be present in a TC Transfer Frame" (6.2.4) and "The randomizer defined here shall be used in all CLTUs passed to the physical layer" (8.4.2). Both are on by default. The GUI still lets you switch them off for CCSDS-only missions, and shows a warning naming the ECSS clause when you do.

**Note 4: Physical layer.** The organisers provided no reference vector for this layer. It follows the PLOP sequence definitions in [SCC] and [E50] clause 9. RF modulation is outside the software scope.

## 4. Scope

**Implemented:** packetization (with optional PUS-C secondary header builder), segmentation, AD/BD/BC transfer frames with optional FECF, fill, randomizer, BCH(63,56), CLTU, PLOP acquisition and idle sequences, a decoder-side self-check, and reference-vector validation.

**Not implemented (outside the challenge baseline):** LDPC coding, COP-1/FARM sequence-controlled retransmission, segmentation of packets across several frames, and RF modulation.
