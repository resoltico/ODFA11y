# SPDX-License-Identifier: MPL-2.0
"""Capture one source beside its dependencies without relocating relative references."""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def capture_source(source: Path) -> Generator[Path]:
    """Copy source bytes once to a private file in the original resource directory.

    The context owns cleanup. The source directory must permit temporary
    files. External dependencies are not captured and require stable, isolated inputs.

    Yields
    ------
    Path
        The captured document, with its original suffix and relative resource base.

    """
    captured_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".odfa11y-source-", suffix=source.suffix, dir=source.parent, delete=False
        ) as captured:
            captured_path = Path(captured.name)
            # Read the source once; later stages use only the captured bytes.
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, captured)
        # Close before reopening on Windows, where an open temporary file may be locked.
        yield captured_path
    finally:
        if captured_path is not None:
            captured_path.unlink(missing_ok=True)
