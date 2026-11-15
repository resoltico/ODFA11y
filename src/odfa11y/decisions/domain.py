# SPDX-License-Identifier: MPL-2.0
"""Canonical target enumeration, exact resolution and content identity."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from lxml import etree

from odfa11y.errors import DocumentRefusal
from odfa11y.odf import OdfDocument
from odfa11y.targets import Fingerprint, Target, TargetPath


@dataclass(frozen=True, slots=True)
class TargetDomain:
    """One authoritative source of a concept's target paths and fingerprints."""

    enumerate: Callable[[OdfDocument], Iterable[tuple[TargetPath, etree._Element]]]
    fingerprint: Callable[[OdfDocument, etree._Element], Fingerprint]

    def resolve(self, document: OdfDocument, path: TargetPath) -> etree._Element:
        matches = [node for candidate, node in self.enumerate(document) if candidate == path]
        if len(matches) != 1:
            message = f"Target {path!r} must resolve to exactly one source element"
            raise DocumentRefusal(message)
        return matches[0]

    def binding(self, document: OdfDocument, path: TargetPath) -> Target:
        return Target(path, self.fingerprint(document, self.resolve(document, path)))
