"""Transfer layer: build the CCSDS TC Transfer Frame.

Standard references: CCSDS 232.0-B-4, TC Space Data Link Protocol;
ECSS-E-ST-50-04C (31 July 2008) clauses 5 and 6, the version supplied by the organisers.

  +---------------------------- primary header (5 bytes) ----------------------------+
  | version 2b | bypass 1b | control cmd 1b | spare 2b | SCID 10b | VCID 6b | frame length 10b | seq no. 8b |
  +----------------------------------------------------------------------------------+
  | data field: segment header (1 byte) + packet          | FECF, CRC-16 (2 bytes, optional) |

The Frame Length field holds (total frame length in octets) - 1.
The whole frame may be at most 1024 octets.
"""

from dataclasses import dataclass

from .crc import crc16_bytes

MAX_FRAME_LENGTH = 1024
PRIMARY_HEADER_LENGTH = 5

# Frame types: (bypass flag, control command flag)
FRAME_TYPES = {
    "AD": (0, 0),   # sequence-controlled (COP-1) data
    "BD": (1, 0),   # expedited data, bypasses the acceptance checks
    "BC": (1, 1),   # control command for the on-board FARM (e.g. Unlock, Set V(R))
}
# (bypass 0, control 1) is not a valid combination in the standard.

# Segment header: hard-coded as agreed with the hackathon focal person.
# Sequence flags '11' = the segment holds a complete, unsegmented packet.
SEGMENT_SEQUENCE_FLAGS = 0b11
DEFAULT_MAP_ID = 0b111111   # 63, as in the organisers' configuration


@dataclass
class TransferFrameConfig:
    spacecraft_id: int = 0b1000010011   # 10 bits (531, from the organisers' configuration)
    virtual_channel_id: int = 18        # 6 bits
    frame_sequence_number: int = 0      # 8 bits
    frame_type: str = "BD"              # "AD", "BD" or "BC"
    version: int = 0                    # 2 bits, always 00 in CCSDS 232.0
    map_id: int = DEFAULT_MAP_ID        # 6 bits, in the segment header
    use_fecf: bool = True               # append the Frame Error Control Field


def build_segment(packet: bytes, map_id: int) -> bytes:
    """Prefix the packet with the 1-byte segment header (sequence flags | MAP ID)."""
    _check_range("MAP ID", map_id, 0, 63)
    return bytes([(SEGMENT_SEQUENCE_FLAGS << 6) | map_id]) + packet


def build_primary_header(cfg: TransferFrameConfig, frame_length: int) -> bytes:
    """Return the 5-byte primary header. `frame_length` is the full frame size in octets."""
    if cfg.frame_type not in FRAME_TYPES:
        raise ValueError("Frame type must be AD, BD or BC")
    bypass, control = FRAME_TYPES[cfg.frame_type]
    _check_range("Frame version", cfg.version, 0, 3)
    _check_range("Spacecraft ID", cfg.spacecraft_id, 0, 0x3FF)
    _check_range("Virtual channel ID", cfg.virtual_channel_id, 0, 0x3F)
    _check_range("Frame sequence number", cfg.frame_sequence_number, 0, 0xFF)
    _check_range("Frame length", frame_length, PRIMARY_HEADER_LENGTH + 1, MAX_FRAME_LENGTH)

    # 16 bits: version | bypass | control command | spare (00) | SCID
    word1 = (cfg.version << 14) | (bypass << 13) | (control << 12) | cfg.spacecraft_id
    # 16 bits: VCID | frame length - 1
    word2 = (cfg.virtual_channel_id << 10) | (frame_length - 1)
    return word1.to_bytes(2, "big") + word2.to_bytes(2, "big") \
        + bytes([cfg.frame_sequence_number])


def build_transfer_frame(data_field: bytes, cfg: TransferFrameConfig) -> bytes:
    """Return the complete TC Transfer Frame around `data_field`.

    For AD and BD frames `data_field` is the segment (segment header + packet).
    For BC frames it is the control command itself, which has no segment header.
    """
    fecf_length = 2 if cfg.use_fecf else 0
    frame_length = PRIMARY_HEADER_LENGTH + len(data_field) + fecf_length
    if frame_length > MAX_FRAME_LENGTH:
        raise ValueError("Frame would be %d octets; CCSDS 232.0 allows at most %d"
                         % (frame_length, MAX_FRAME_LENGTH))
    frame = build_primary_header(cfg, frame_length) + data_field
    if cfg.use_fecf:
        frame += crc16_bytes(frame)       # FECF covers the whole frame before it
    return frame


def _check_range(name: str, value: int, low: int, high: int) -> None:
    if not isinstance(value, int) or not (low <= value <= high):
        raise ValueError("%s must be between %d and %d (got %r)" % (name, low, high, value))
