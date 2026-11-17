# SPDX-License-Identifier: AGPL-3.0-only
"""Read the Writer corpus manifest: each document's expectations and recorded identity."""

import tomllib
from dataclasses import dataclass
lazy from pathlib import Path

from odfa11y.families.text.flow import visible_text_snapshot
from odfa11y.odf import OdfDocument, Part
from tests.fixtures.paths import TESTS

CORPUS = TESTS / "corpus"
DOCUMENT_SUFFIXES = frozenset({".odt", ".fodt"})


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """One stored ODF identity, its purposes and independently recorded expectations."""

    file: str
    family: str
    purposes: tuple[str, ...]
    producer: str
    sha256: str
    schema_violations: int
    builder: str
    rules: frozenset[str] = frozenset()
    rules_after_plan: frozenset[str] = frozenset()
    source: str | None = None
    filter: str | None = None
    odf_version: str | None = None
    authoring: str | None = None

    @property
    def path(self) -> Path:
        return CORPUS / self.file

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def source_path(self) -> Path | None:
        return CORPUS / self.source if self.source else None


def load_documents() -> tuple[CorpusDocument, ...]:
    """Read the single corpus manifest without deriving its recorded expectations."""
    manifest = tomllib.loads((CORPUS / "manifest.toml").read_text(encoding="utf-8"))
    return tuple(
        CorpusDocument(
            file=entry["file"],
            family=entry["family"],
            purposes=tuple(entry["purposes"]),
            producer=entry["producer"],
            sha256=entry["sha256"],
            schema_violations=entry["schema_violations"],
            builder=entry["builder"],
            rules=frozenset(entry.get("rules", ())),
            rules_after_plan=frozenset(entry.get("rules_after_plan", ())),
            source=entry.get("source"),
            filter=entry.get("filter"),
            odf_version=entry.get("odf_version"),
            authoring=entry.get("authoring"),
        )
        for entry in manifest["document"]
    )


ALL_DOCUMENTS = load_documents()
DOCUMENTS = tuple(
    document for document in ALL_DOCUMENTS if "writer-regression" in document.purposes
)
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
    blocks = (
        _squeezed(block)
        for block in visible_text_snapshot(OdfDocument.open(path).tree(Part.CONTENT))
    )
    return tuple(block for block in blocks if block)


def _squeezed(text: str) -> str:
    return "".join(text.split())
