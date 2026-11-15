# SPDX-License-Identifier: MPL-2.0
"""Native sheet-name syntax shared by answer contracts and source checks."""

FORBIDDEN_CHARACTERS = frozenset("[]*?:/\\")


def invalid_name_reason(name: str) -> str | None:
    """Explain why a name cannot be a sheet name.

    Returns
    -------
    str | None
        The reason, or None for a usable name: not blank, free of square brackets, ``*``,
        ``?``, ``:``, ``/`` and backslash, and without an apostrophe at either end.

    """
    if not name.strip():
        return "it is empty"
    if FORBIDDEN_CHARACTERS & set(name):
        return "it contains one of [ ] * ? : / \\"
    if name.startswith("'") or name.endswith("'"):
        return "it starts or ends with an apostrophe"
    return None
