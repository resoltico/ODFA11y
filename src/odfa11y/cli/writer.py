# SPDX-License-Identifier: AGPL-3.0-only
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
