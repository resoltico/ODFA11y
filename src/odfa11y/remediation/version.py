# SPDX-License-Identifier: MPL-2.0
"""Declare a different ODF version on every part of a document."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import SUPPORTED_VERSIONS, Part, is_office_element, qn, select_elements

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

VERSIONED_PARTS = (Part.CONTENT, Part.STYLES, Part.META, Part.SETTINGS)


@dataclass(frozen=True, slots=True)
class SetOdfVersion(Operation):
    """Relabel the document as a bundled schema version; validation then checks the result."""

    version: str
    name: ClassVar[str] = "set_odf_version"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        if self.version not in SUPPORTED_VERSIONS:
            return (
                Outcome(
                    self.name,
                    Status.FAILED,
                    f"ODF {self.version} has no bundled schema; use one of {SUPPORTED_VERSIONS}.",
                ),
            )
        changed = 0
        for part in VERSIONED_PARTS:
            if document.has(part):
                root = document.tree(part).getroot()
                if is_office_element(root) and root.get(qn("office", "version")) != self.version:
                    document.edit(part).getroot().set(qn("office", "version"), self.version)
                    changed += 1
        changed += self._relabel_manifest(document)
        if not changed:
            return (Outcome(self.name, Status.UNCHANGED, f"Already declares ODF {self.version}."),)
        return (
            Outcome(
                self.name,
                Status.APPLIED,
                f"Declared ODF {self.version} in {changed} place(s).",
                count=changed,
            ),
        )

    def _relabel_manifest(self, document: OdfDocument) -> int:
        if not document.has(Part.MANIFEST):
            return 0
        manifest = document.tree(Part.MANIFEST).getroot()
        entries = select_elements(manifest, "./manifest:file-entry[@manifest:full-path='/']")
        targets = [manifest, *entries]
        stale = [node for node in targets if node.get(qn("manifest", "version")) != self.version]
        if not stale:
            return 0
        document.edit(Part.MANIFEST)
        for node in stale:
            node.set(qn("manifest", "version"), self.version)
        return len(stale)
