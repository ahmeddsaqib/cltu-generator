"""Packetization: build the PUS telecommand as a CCSDS Space Packet.

Standard references:
  - CCSDS 133.0-B-2, Space Packet Protocol (the 6-byte primary header)
  - ECSS-E-ST-70-41C, PUS telecommand packet (secondary header, Packet Error Control)

Layout produced here:

  +----------------------------- primary header (6 bytes) -----------------------------+
  | version 3b | type 1b | sec.hdr flag 1b | APID 11b | seq flags 2b | seq count 14b | data length 16b |
  +-------------------------------------------------------------------------------------+
  | packet data field: [PUS secondary header] + application data      | optional CRC (2 bytes) |
"""

from dataclasses import dataclass

from .crc import crc16_bytes

PACKET_TYPE_TELECOMMAND = 1

# Packet Data Length field = (number of data bytes) - 1. The 2-byte CRC is NOT counted,
# as the hackathon focal person instructed (8 Oct 2026); the test vector agrees
# (10 data bytes + 2 CRC bytes -> field value 9). Note: CCSDS 133.0-B-2 itself
# would count the CRC too (giving 11).


@dataclass
class PusSecondaryHeader:
    """Optional helper: the PUS TC secondary header (ECSS-E-ST-70-41C, PUS-C).

    If used, it is placed at the start of the packet data field:
      PUS version (4 bits) | acknowledgement flags (4 bits) | service type (8 bits)
      | message subtype (8 bits) | source ID (0, 1 or 2 bytes, mission choice)
    """
    pus_version: int = 2          # 2 = PUS-C (ECSS-E-ST-70-41C), 1 = PUS-A
    ack_flags: int = 0b0000       # which acknowledgement reports the ground wants
    service_type: int = 17        # e.g. 17 = test service
    service_subtype: int = 1      # e.g. 1 = "are you alive?" connection test
    source_id: int = 0
    source_id_bytes: int = 2

    def to_bytes(self) -> bytes:
        _check_range("PUS version", self.pus_version, 0, 15)
        _check_range("Acknowledgement flags", self.ack_flags, 0, 15)
        _check_range("Service type", self.service_type, 0, 255)
        _check_range("Service subtype", self.service_subtype, 0, 255)
        if self.source_id_bytes not in (0, 1, 2):
            raise ValueError("Source ID length must be 0, 1 or 2 bytes")
        _check_range("Source ID", self.source_id, 0, (1 << (8 * self.source_id_bytes)) - 1)
        header = bytes([(self.pus_version << 4) | self.ack_flags,
                        self.service_type,
                        self.service_subtype])
        return header + self.source_id.to_bytes(self.source_id_bytes, "big")


@dataclass
class SpacePacketConfig:
    apid: int = 234                    # Application Process Identifier, 11 bits
    version: int = 0                   # Packet Version Number, 3 bits (always 0 in CCSDS)
    secondary_header_flag: int = 1     # 1 = a PUS secondary header is present in the data
    sequence_flags: int = 0b11         # 2 bits; 11 = unsegmented (stand-alone) packet
    sequence_count: int = 0x3FFF       # 14 bits
    error_control: bool = True         # append the 2-byte Packet Error Control (CRC-16)


def build_space_packet(data_field: bytes, cfg: SpacePacketConfig) -> bytes:
    """Return the complete telecommand packet: primary header + data + optional CRC."""
    _check_range("Packet version", cfg.version, 0, 7)
    _check_range("APID", cfg.apid, 0, 0x7FF)
    _check_range("Secondary header flag", cfg.secondary_header_flag, 0, 1)
    _check_range("Sequence flags", cfg.sequence_flags, 0, 3)
    _check_range("Sequence count", cfg.sequence_count, 0, 0x3FFF)
    if len(data_field) == 0:
        raise ValueError("The packet data field must contain at least one byte")

    length_field = len(data_field) - 1     # data bytes - 1, CRC not counted
    _check_range("Packet data length", length_field, 0, 0xFFFF)

    # First 16 bits: version | type | secondary header flag | APID
    word1 = (cfg.version << 13) | (PACKET_TYPE_TELECOMMAND << 12) \
        | (cfg.secondary_header_flag << 11) | cfg.apid
    # Next 16 bits: sequence flags | sequence count
    word2 = (cfg.sequence_flags << 14) | cfg.sequence_count

    packet = word1.to_bytes(2, "big") + word2.to_bytes(2, "big") \
        + length_field.to_bytes(2, "big") + data_field
    if cfg.error_control:
        packet += crc16_bytes(packet)     # CRC covers the whole packet before it
    return packet


def _check_range(name: str, value: int, low: int, high: int) -> None:
    if not isinstance(value, int) or not (low <= value <= high):
        raise ValueError("%s must be between %d and %d (got %r)" % (name, low, high, value))
