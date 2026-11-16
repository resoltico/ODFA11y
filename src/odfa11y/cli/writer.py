# SPDX-License-Identifier: MPL-2.0
"""The only owner of command stdout and stderr writes."""

import sys
from typing import TextIO


def out(text: str, *, end: str = "\n") -> None:
    sys.stdout.write(text + end)


def err(text: str, *, end: str = "\n", stream: TextIO | None = None, flush: bool = False) -> None:
    target = stream if stream is not None else sys.stderr
    target.write(text + end)
    if flush:
        target.flush()
