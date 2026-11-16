# SPDX-License-Identifier: MPL-2.0
"""Stored-size and traversal limits for PDF inspection; OS isolation remains necessary."""

from dataclasses import dataclass

MAX_PDF_BYTES = 256 * 1024 * 1024
MAX_PDF_PAGES = 5_000
MAX_STRUCTURE_NODES = 500_000
MAX_CONTENT_STREAMS = 10_000
MAX_FORM_DEPTH = 50
MAX_FORM_INVOCATIONS = 5_000

MAX_CONTENT_BYTES = (
    64 * 1024 * 1024
)  # unique consumed decoded streams; invocation work is bounded separately


@dataclass(frozen=True, slots=True)
class Limits:
    stored_bytes: int
    pages: int
    structure_nodes: int
    decoded_bytes: int
    invocation_bytes: int
    content_streams: int
    form_depth: int
    form_invocations: int


def default_limits() -> Limits:
    return Limits(
        MAX_PDF_BYTES,
        MAX_PDF_PAGES,
        MAX_STRUCTURE_NODES,
        MAX_CONTENT_BYTES,
        MAX_CONTENT_BYTES,
        MAX_CONTENT_STREAMS,
        MAX_FORM_DEPTH,
        MAX_FORM_INVOCATIONS,
    )
