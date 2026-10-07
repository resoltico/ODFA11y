# SPDX-License-Identifier: MPL-2.0
"""Read the Writer corpus manifest: each document's expectations and recorded identity."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from odfa11y.families.text import ADAPTER
from odfa11y.odf import OdfDocument

CORPUS = Path(__file__).parent / "corpus"
DOCUMENT_SUFFIXES = frozenset({".odt", ".fodt"})


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """What a corpus document must audit to, and the bytes it must keep."""

    file: str
    rules: frozenset[str]
    rules_after_plan: frozenset[str]
    schema_violations: int
    sha256: str

    @property
    def path(self) -> Path:
        """Where the document is stored."""
        return CORPUS / self.file

    @property
    def stem(self) -> str:
        """The name shared by the package and flat forms of one document."""
        return self.path.stem


def load_documents() -> tuple[CorpusDocument, ...]:
    """Read every document entry of the manifest.

    Returns
    -------
    tuple[CorpusDocument, ...]
        The entries in manifest order.

    """
    manifest = tomllib.loads((CORPUS / "manifest.toml").read_text(encoding="utf-8"))
    return tuple(
        CorpusDocument(
            file=entry["file"],
            rules=frozenset(entry["rules"]),
            rules_after_plan=frozenset(entry["rules_after_plan"]),
            schema_violations=entry["schema_violations"],
            sha256=entry["sha256"],
        )
        for entry in manifest["document"]
    )


DOCUMENTS = load_documents()
DOCUMENT_IDS = [document.file for document in DOCUMENTS]


def visible_text(path: Path) -> tuple[str, ...]:
    """Read a document's visible text blocks without spacing.

    Flat XML keeps the indentation between elements that a package does not, and removing
    spacer paragraphs removes empty blocks; neither changes the words a reader sees.

    Returns
    -------
    tuple[str, ...]
        The non-empty text blocks, each with all whitespace removed.

    """
    blocks = (_squeezed(block) for block in ADAPTER.snapshot(OdfDocument.open(path)))
    return tuple(block for block in blocks if block)


def _squeezed(text: str) -> str:
    return "".join(text.split())
