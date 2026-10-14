# SPDX-License-Identifier: MPL-2.0
"""Keep untrusted human-readable fields from controlling terminal presentation."""

from __future__ import annotations

BYTE_MAX = 0xFF
BIDI_CONTROLS = frozenset({0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)})

UNSAFE_CONTROLS = frozenset({*range(0x20), *range(0x7F, 0xA0), *BIDI_CONTROLS, 0x2028, 0x2029})


def terminal_text(value: object) -> str:
    """Escape terminal and direction controls while preserving ordinary Unicode.

    Returns
    -------
    str
        One safe field, with control characters represented by visible escapes.

    """
    result = []
    for character in str(value):
        code = ord(character)
        if code in UNSAFE_CONTROLS:
            result.append(f"\\x{code:02x}" if code <= BYTE_MAX else f"\\u{code:04x}")
        else:
            result.append(character)
    return "".join(result)
