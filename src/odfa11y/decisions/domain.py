# SPDX-License-Identifier: AGPL-3.0-only
"""Canonical target enumeration, exact resolution and content identity."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from lxml import etree

from odfa11y.errors import PlanError
from odfa11y.odf import OdfDocument
from odfa11y.targets import Fingerprint, Target, TargetPath
lazy from odfa11y.decisions.decision import Decision


@dataclass(slots=True)
class TargetIndex:
    """A read-only target inspection lifetime, discarded before document mutation."""

    nodes: dict[TargetPath, tuple[etree._Element, ...]]
    fingerprint: Callable[[etree._Element], Fingerprint]
    _fingerprints: dict[TargetPath, Fingerprint] = field(default_factory=dict)

    def resolve(self, path: TargetPath) -> etree._Element:
        matches = self.nodes.get(path, ())
        if len(matches) != 1:
            message = f"Target {path!r} must resolve to exactly one source element"
            raise PlanError(message)
        return matches[0]

    def binding(self, path: TargetPath) -> Target:
        node = self.resolve(path)
        if path not in self._fingerprints:
            self._fingerprints[path] = self.fingerprint(node)
        return Target(path, self._fingerprints[path])


@dataclass(frozen=True, slots=True)
class TargetDomain:
    """One authoritative source of a concept's target paths and fingerprints."""

    enumerate: Callable[[OdfDocument], Iterable[tuple[TargetPath, etree._Element]]]
    fingerprint: Callable[[OdfDocument, etree._Element], Fingerprint]

    fingerprint_context: Callable[[OdfDocument], Callable[[etree._Element], Fingerprint]] | None = (
        None
    )

    def inspect(self, document: OdfDocument) -> TargetIndex:
        grouped: dict[TargetPath, list[etree._Element]] = {}
        for path, node in self.enumerate(document):
            grouped.setdefault(path, []).append(node)
        fingerprint = (
            self.fingerprint_context(document)
            if self.fingerprint_context
            else lambda node: self.fingerprint(document, node)
        )
        return TargetIndex({path: tuple(nodes) for path, nodes in grouped.items()}, fingerprint)

    def resolve(self, document: OdfDocument, path: TargetPath) -> etree._Element:
        return self.inspect(document).resolve(path)

    def binding(self, document: OdfDocument, path: TargetPath) -> Target:
        return self.inspect(document).binding(path)


def resolved_node(document: OdfDocument, decision: Decision) -> etree._Element:
    """Resolve a validated targeted decision through its concept's sole domain."""
    if decision.kind.domain is None or decision.target is None:
        message = f"Decision {decision.kind.id!r} requires a target domain"
        raise PlanError(message)
    return decision.kind.domain.resolve(document, decision.target.path)
