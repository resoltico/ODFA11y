# SPDX-License-Identifier: MPL-2.0
"""Stored-size and traversal limits for PDF inspection; OS isolation remains necessary."""

from pathlib import Path

from odfa11y.errors import ToolFailure

MAX_PDF_BYTES = 256 * 1024 * 1024
MAX_PDF_PAGES = 5_000
MAX_STRUCTURE_NODES = 500_000
MAX_CONTENT_BYTES = (
    64 * 1024 * 1024
)  # unique consumed decoded streams; invocation work is bounded separately


def check_file_size(path: str | Path) -> None:
    """Refuse a PDF file larger than the size limit before it is parsed.

    Raises
    ------
    ToolFailure
        The file is larger than ``MAX_PDF_BYTES``.

    """
    if Path(path).stat().st_size > MAX_PDF_BYTES:
        msg = f"PDF {Path(path).name} exceeds the {MAX_PDF_BYTES}-byte limit"
        raise ToolFailure(msg)


def check_limits(path: str | Path, pages: int) -> None:
    """Refuse a PDF with more pages than the limit.

    Raises
    ------
    ToolFailure
        The page count exceeds ``MAX_PDF_PAGES``.

    """
    check_file_size(path)
    if pages > MAX_PDF_PAGES:
        msg = f"PDF {Path(path).name} has {pages} pages; the limit is {MAX_PDF_PAGES}"
        raise ToolFailure(msg)
