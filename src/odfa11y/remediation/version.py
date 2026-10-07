# SPDX-License-Identifier: MPL-2.0
"""Declare a different ODF version on every package member."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.odf import SUPPORTED_VERSIONS, qn, select_elements

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from odfa11y.odf import OdtDocument

VERSIONED_MEMBERS = ("content.xml", "styles.xml", "meta.xml", "settings.xml")


@dataclass(frozen=True, slots=True)
class SetOdfVersion(Operation):
    """Relabel the package as a bundled schema version; validation then checks the result."""

    version: str
    name: ClassVar[str] = "set_odf_version"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        if self.version not in SUPPORTED_VERSIONS:
            return (
                Outcome(
                    self.name,
                    Status.FAILED,
                    f"ODF {self.version} has no bundled schema; use one of {SUPPORTED_VERSIONS}.",
                ),
            )
        changed = 0
        for member in VERSIONED_MEMBERS:
            if document.has(member):
                root = document.tree(member).getroot()
                if root.get(qn("office", "version")) != self.version:
                    document.edit(member).getroot().set(qn("office", "version"), self.version)
                    changed += 1
        manifest = document.tree("META-INF/manifest.xml").getroot()
        entries = select_elements(manifest, "./manifest:file-entry[@manifest:full-path='/']")
        targets = [manifest, *entries]
        if any(node.get(qn("manifest", "version")) != self.version for node in targets):
            document.edit("META-INF/manifest.xml")
            for node in targets:
                if node.get(qn("manifest", "version")) != self.version:
                    node.set(qn("manifest", "version"), self.version)
                    changed += 1
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
