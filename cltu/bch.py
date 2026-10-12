"""BCH(63,56) channel coding for TC (CCSDS 231.0-B-4, section 3).

Each codeblock is 8 bytes:
  7 information bytes (56 bits)
  + 7 parity bits (computed with g(x) = x^7 + x^6 + x^2 + 1, then complemented)
  + 1 filler bit, always 0

The parity is the remainder of dividing the 56 information bits (times x^7) by g(x).
This is done with a 7-bit shift register, exactly like the hardware encoder.
"""

INFO_BYTES = 7
CODEBLOCK_BYTES = 8

# g(x) = x^7 + x^6 + x^2 + 1. The x^7 term is implicit in the 7-bit register,
# the remaining terms x^6 + x^2 + 1 give the feedback mask 100 0101 = 0x45.
GENERATOR_MASK = 0x45


def parity_bits(info: bytes) -> int:
    """Return the 7-bit remainder (before complementing) for 7 information bytes."""
    if len(info) != INFO_BYTES:
        raise ValueError("A BCH codeblock needs exactly 7 information bytes")
    register = 0
    for byte in info:
        for i in range(7, -1, -1):                 # most significant bit first
            bit = (byte >> i) & 1
            feedback = ((register >> 6) & 1) ^ bit
            register = (register << 1) & 0x7F
            if feedback:
                register ^= GENERATOR_MASK
    return register


def parity_byte(info: bytes) -> bytes:
    """Return the 8th byte of the codeblock: complemented parity bits + filler bit 0."""
    complemented = (~parity_bits(info)) & 0x7F
    return bytes([complemented << 1])              # filler bit (0) in the last position


def encode_codeblock(info: bytes) -> bytes:
    """Return one 8-byte codeblock."""
    return bytes(info) + parity_byte(info)


def encode(data: bytes) -> bytes:
    """Encode data whose length is a multiple of 7 into consecutive codeblocks."""
    if len(data) % INFO_BYTES:
        raise ValueError("Data must be padded to a multiple of 7 bytes before BCH encoding")
    out = bytearray()
    for i in range(0, len(data), INFO_BYTES):
        out += encode_codeblock(data[i:i + INFO_BYTES])
    return bytes(out)
