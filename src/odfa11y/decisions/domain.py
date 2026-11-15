# SPDX-License-Identifier: MPL-2.0
"""Canonical target enumeration, exact resolution and content identity."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from lxml import etree

from odfa11y.errors import PlanError
from odfa11y.odf import OdfDocument
from odfa11y.targets import Fingerprint, Target, TargetPath
lazy from odfa11y.decisions.decision import Decision


@dataclass(frozen=True, slots=True)
class TargetDomain:
    """One authoritative source of a concept's target paths and fingerprints."""

    enumerate: Callable[[OdfDocument], Iterable[tuple[TargetPath, etree._Element]]]
    fingerprint: Callable[[OdfDocument, etree._Element], Fingerprint]

    def resolve(self, document: OdfDocument, path: TargetPath) -> etree._Element:
        matches = [node for candidate, node in self.enumerate(document) if candidate == path]
        if len(matches) != 1:
            message = f"Target {path!r} must resolve to exactly one source element"
            raise PlanError(message)
        return matches[0]

    def binding(self, document: OdfDocument, path: TargetPath) -> Target:
        return Target(path, self.fingerprint(document, self.resolve(document, path)))


def resolved_node(document: OdfDocument, decision: Decision) -> etree._Element:
    """Resolve a validated targeted decision through its concept's sole domain."""
    if decision.kind.domain is None or decision.target is None:
        message = f"Decision {decision.kind.id!r} requires a target domain"
        raise PlanError(message)
    return decision.kind.domain.resolve(document, decision.target.path)
