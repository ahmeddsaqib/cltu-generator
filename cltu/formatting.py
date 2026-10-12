"""Helpers to show bytes as hex or binary text, and to read hex typed by a user."""

import re


def to_hex(data: bytes, per_line: int = 16) -> str:
    """'EB 90 DD ...', wrapped every `per_line` bytes."""
    parts = ["%02X" % b for b in data]
    lines = [" ".join(parts[i:i + per_line]) for i in range(0, len(parts), per_line)]
    return "\n".join(lines)


def to_binary(data: bytes, per_line: int = 8) -> str:
    """'11101011 10010000 ...', wrapped every `per_line` bytes."""
    parts = ["{:08b}".format(b) for b in data]
    lines = [" ".join(parts[i:i + per_line]) for i in range(0, len(parts), per_line)]
    return "\n".join(lines)


def parse_hex(text: str) -> bytes:
    """Accept '01 02 0A', '01020A', '0x01, 0x02' and similar. Raises ValueError if invalid."""
    cleaned = re.sub(r"0[xX]", "", text)
    cleaned = re.sub(r"[\s,;:_-]", "", cleaned)
    if not cleaned:
        return b""
    if not re.fullmatch(r"[0-9A-Fa-f]+", cleaned):
        raise ValueError("Only hexadecimal digits 0-9 and A-F are allowed")
    if len(cleaned) % 2:
        raise ValueError("Hex data must have an even number of digits (two per byte)")
    return bytes.fromhex(cleaned)


def parse_int(text: str) -> int:
    """Accept decimal (234), hex (0xEA) or binary (0b11101010), with optional '_' separators."""
    value = text.strip().replace("_", "")
    if not value:
        raise ValueError("A number is required")
    if value.isdigit():
        return int(value, 10)          # plain decimal, leading zeros allowed
    return int(value, 0)
