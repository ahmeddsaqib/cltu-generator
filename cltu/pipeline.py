"""The complete processing chain, with every intermediate stage recorded.

  Packetization   PUS data -> Space Packet (+ packet CRC)
  Transfer layer  segment header + packet -> TC Transfer Frame (+ FECF)
  Sync & coding   fill -> randomize -> BCH -> start/tail -> CLTU
  Physical layer  acquisition sequence + CLTU + idle sequence
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .physical import PhysicalConfig, build_physical_stream, warnings_for
from .space_packet import PusSecondaryHeader, SpacePacketConfig, build_space_packet
from .sync_coding import CodingConfig, build_cltu
from .transfer_frame import TransferFrameConfig, build_segment, build_transfer_frame

INPUT_PUS_DATA = "pus_data"          # user gives the packet data field; header is built
INPUT_RAW_PACKET = "raw_packet"      # user gives a complete Space Packet
INPUT_CONTROL_COMMAND = "control"    # BC frame: user gives the control command bytes


@dataclass
class GeneratorConfig:
    input_mode: str = INPUT_PUS_DATA
    user_data: bytes = bytes(range(1, 11))          # meaning depends on input_mode
    secondary_header: Optional[PusSecondaryHeader] = None
    packet: SpacePacketConfig = field(default_factory=SpacePacketConfig)
    frame: TransferFrameConfig = field(default_factory=TransferFrameConfig)
    coding: CodingConfig = field(default_factory=CodingConfig)
    physical: PhysicalConfig = field(default_factory=PhysicalConfig)


@dataclass
class Stage:
    layer: str
    name: str
    data: bytes
    note: str = ""


@dataclass
class Result:
    stages: List[Stage]
    packet: bytes
    frame: bytes
    cltu: bytes
    physical: bytes
    warnings: List[str]

    def stage(self, name: str) -> Stage:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(name)


def run(cfg: GeneratorConfig) -> Result:
    stages: List[Stage] = []
    warnings: List[str] = []

    # ---- Packetization -------------------------------------------------------
    if cfg.input_mode == INPUT_CONTROL_COMMAND:
        if cfg.frame.frame_type != "BC":
            raise ValueError("Control command input needs frame type BC")
        if not cfg.user_data:
            raise ValueError("Enter the control command bytes")
        packet = b""
        data_field = cfg.user_data                     # BC frames carry no segment header
        # ECSS-E-ST-50-04C clause 7.8 defines the two COP-1 control commands
        if data_field != b"\x00" and not (len(data_field) == 3 and data_field[:2] == b"\x82\x00"):
            warnings.append("Not a standard COP-1 control command: Unlock is 00, "
                            "Set V(R) is 82 00 followed by the new V(R) (ECSS-E-ST-50-04C 7.8).")
        stages.append(Stage("Transfer", "Control command", data_field,
                            "BC frame: control command, no segment header"))
    else:
        if cfg.frame.frame_type == "BC":
            raise ValueError("Frame type BC carries a control command, not a packet")
        if cfg.input_mode == INPUT_RAW_PACKET:
            if len(cfg.user_data) < 7:
                raise ValueError("A Space Packet is at least 7 bytes (6-byte header + data)")
            packet = cfg.user_data
            stages.append(Stage("Packet", "PUS packet", packet, "supplied by the user"))
        elif cfg.input_mode == INPUT_PUS_DATA:
            data = cfg.user_data
            if cfg.secondary_header is not None:
                sec = cfg.secondary_header.to_bytes()
                stages.append(Stage("Packet", "PUS secondary header", sec))
                data = sec + data
            packet = build_space_packet(data, cfg.packet)
            stages.append(Stage("Packet", "Packet primary header", packet[:6]))
            stages.append(Stage("Packet", "Packet data field", data))
            if cfg.packet.error_control:
                stages.append(Stage("Packet", "Packet CRC", packet[-2:], "CRC-16 over header + data"))
            stages.append(Stage("Packet", "PUS packet", packet))
        else:
            raise ValueError("Unknown input mode: %r" % cfg.input_mode)

        data_field = build_segment(packet, cfg.frame.map_id)
        stages.append(Stage("Transfer", "Segment", data_field,
                            "segment header (sequence flags 11 + MAP ID) + packet"))

    # ---- Transfer layer ------------------------------------------------------
    frame = build_transfer_frame(data_field, cfg.frame)
    stages.append(Stage("Transfer", "Frame primary header", frame[:5]))
    if cfg.frame.use_fecf:
        stages.append(Stage("Transfer", "FECF", frame[-2:], "CRC-16 over the whole frame"))
    stages.append(Stage("Transfer", "TC Transfer Frame", frame))

    # ---- Synchronization and channel coding ----------------------------------
    coded = build_cltu(frame, cfg.coding)
    fill = len(coded.filled) - len(frame)
    stages.append(Stage("Coding", "Frame + fill", coded.filled, "%d fill byte(s) of 0x55" % fill))
    if cfg.coding.randomizer:
        stages.append(Stage("Coding", "Randomized data", coded.randomized))
    stages.append(Stage("Coding", "BCH codeblocks", b"".join(coded.codeblocks),
                        "%d codeblocks of 7 data bytes + 1 parity byte" % len(coded.codeblocks)))
    stages.append(Stage("Coding", "CLTU", coded.cltu, "EB 90 + codeblocks + tail sequence"))

    # ---- Physical layer ------------------------------------------------------
    physical = build_physical_stream(coded.cltu, cfg.physical)
    warnings.extend(warnings_for(cfg.physical))
    # ECSS-E-ST-50-04C (the organisers' reference standard) makes two CCSDS options mandatory
    if not cfg.frame.use_fecf:
        warnings.append("ECSS-E-ST-50-04C requires the Frame Error Control Field (clause 6.2.4).")
    if not cfg.coding.randomizer:
        warnings.append("ECSS-E-ST-50-04C requires randomization in all CLTUs (clause 8.4.2).")
    stages.append(Stage("Physical", "Physical layer stream", physical,
                        "acquisition sequence + CLTU + idle sequence"))

    return Result(stages=stages, packet=packet, frame=frame, cltu=coded.cltu,
                  physical=physical, warnings=warnings)
