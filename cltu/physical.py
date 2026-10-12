"""Physical layer: Physical Layer Operations Procedure (PLOP), CCSDS 231.0-B-4 section 7
and ECSS-E-ST-50-04C clause 9.

Before a CLTU is sent, the ground station transmits an Acquisition Sequence so that the
spacecraft receiver can lock on to the bit timing. Between or after CLTUs, an Idle
Sequence keeps it locked. Both are alternating ones and zeros.

  bit stream = Acquisition Sequence + CLTU + Idle Sequence

  Acquisition Sequence: at least 128 bits = 16 octets (ECSS-E-ST-50-04C clause 9.2.1;
                        CCSDS 231.0 gives this as the preferred minimum)
  Idle Sequence:        at least 8 bits

  PLOP-1: the carrier is switched off after each CLTU.
  PLOP-2: the carrier stays on; Idle Sequence fills the gaps between CLTUs
          (at least one octet between CLTUs, ECSS-E-ST-50-04C clause 9.3).

The lengths are mission parameters, so they are configurable here.
Modulation onto the RF carrier is outside the scope of this software.
"""

from dataclasses import dataclass

ALTERNATING_01 = 0x55   # 0101 0101
ALTERNATING_10 = 0xAA   # 1010 1010

MIN_ACQUISITION_OCTETS = 16
MIN_IDLE_OCTETS = 1


@dataclass
class PhysicalConfig:
    acquisition_octets: int = 16
    idle_octets: int = 1
    pattern: int = ALTERNATING_01


def build_physical_stream(cltu: bytes, cfg: PhysicalConfig) -> bytes:
    if cfg.pattern not in (ALTERNATING_01, ALTERNATING_10):
        raise ValueError("Pattern must be alternating ones and zeros (0x55 or 0xAA)")
    if cfg.acquisition_octets < 0 or cfg.idle_octets < 0:
        raise ValueError("Sequence lengths cannot be negative")
    acquisition = bytes([cfg.pattern] * cfg.acquisition_octets)
    idle = bytes([cfg.pattern] * cfg.idle_octets)
    return acquisition + cltu + idle


def warnings_for(cfg: PhysicalConfig):
    """Return human-readable warnings when lengths are below the standard's guidance."""
    notes = []
    if cfg.acquisition_octets < MIN_ACQUISITION_OCTETS:
        notes.append("Acquisition sequence is shorter than 128 bits (16 octets), the ECSS-E-ST-50-04C minimum.")
    if cfg.idle_octets < MIN_IDLE_OCTETS:
        notes.append("Idle Sequence is shorter than the minimum of 8 bits.")
    return notes
