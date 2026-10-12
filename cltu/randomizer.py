"""Pseudo-randomizer for TC (CCSDS 231.0-B-4, section 6).

The data is XORed with a fixed pseudo-random bit sequence so that the transmitted
signal has plenty of 0/1 transitions. XOR is its own inverse, so running the same
function again de-randomizes.

Sequence generator:
  polynomial  h(x) = x^8 + x^6 + x^4 + x^3 + x^2 + x + 1
  start state all ones, restarted at the beginning of every CLTU
  repeats every 255 bits
  first 40 bits (quoted in the standard): 1111 1111 0011 1001 1001 1110 0101 1010 0110 1000
                                         = FF 39 9E 5A 68
"""


def random_sequence(length: int) -> bytes:
    """Return the first `length` bytes of the CCSDS TC pseudo-random sequence."""
    register = 0xFF                      # 8-bit shift register, all ones
    out = bytearray()
    for _ in range(length):
        byte = 0
        for _ in range(8):
            output_bit = register & 1    # the bit leaving the register is the next sequence bit
            byte = (byte << 1) | output_bit
            # Feedback: XOR of the register stages given by the polynomial taps
            feedback = (register ^ (register >> 1) ^ (register >> 2)
                        ^ (register >> 3) ^ (register >> 4) ^ (register >> 6)) & 1
            register = (register >> 1) | (feedback << 7)
        out.append(byte)
    return bytes(out)


def randomize(data: bytes) -> bytes:
    """XOR `data` with the pseudo-random sequence (also used to de-randomize)."""
    return bytes(d ^ r for d, r in zip(data, random_sequence(len(data))))


derandomize = randomize
