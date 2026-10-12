"""CRC-16 used by CCSDS (TC Transfer Frame FECF) and by PUS (Packet Error Control).

Standard references:
  - CCSDS 232.0-B-4 and ECSS-E-ST-50-04C clause 6.5, Frame Error Control Field (FECF)
  - ECSS-E-ST-70-41C, Packet Error Control (CRC option)

Both use the same CRC:
  generator polynomial  g(x) = x^16 + x^12 + x^5 + 1   (hex 0x1021)
  initial register      all ones                        (hex 0xFFFF)
  bits processed MSB first, no final inversion.

A well-known check: the CRC of the ASCII text "123456789" is 0x29B1.
"""

POLYNOMIAL = 0x1021
INITIAL_VALUE = 0xFFFF


def crc16(data: bytes, initial: int = INITIAL_VALUE) -> int:
    """Return the 16-bit CRC of `data`."""
    crc = initial
    for byte in data:
        crc ^= byte << 8              # bring the next byte into the top of the register
        for _ in range(8):            # process its 8 bits, most significant first
            if crc & 0x8000:
                crc = ((crc << 1) ^ POLYNOMIAL) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def crc16_bytes(data: bytes) -> bytes:
    """Return the CRC as two bytes, most significant byte first (as it is transmitted)."""
    return crc16(data).to_bytes(2, "big")
