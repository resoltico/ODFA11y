# SPDX-License-Identifier: MPL-2.0
"""Copy a reference paragraph style's spacing onto selected paragraph styles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.errors import RemediationError
from odfa11y.odf import Family, Part, qn

from .contexts import text_nodes
from .derived_styles import (
    NO_STYLE,
    adopt_style,
    derive_paragraph_style,
    derived_style_name,
    is_generated_from,
    set_spacing,
)
from .style_properties import paragraph_style_name
from .styles import catalog_of
from .text import element_text

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

    from .styles import StyleCatalog


@dataclass(frozen=True, slots=True)
class NormalizeSpacing(Operation):
    """Give paragraphs of the target styles the effective spacing of a reference paragraph.

    Spacing is copied onto a derived style named after its base style and a digest of that
    name (``A11ySpacing_<style>_<digest>``). A style of that name is reused only when it is
    provably our own earlier output; ODFA11y never overwrites or reinterprets another style.
    """

    reference_text: str
    target_styles: tuple[str, ...]
    exact_reference: bool = False
    include_headings: bool = False
    name: ClassVar[str] = "normalize_spacing"
    family: ClassVar[Family | None] = Family.TEXT

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        try:
            plan = self._plan(document)
        except RemediationError as exc:
            return (self._failed(str(exc)),)
        if isinstance(plan, tuple):
            return plan
        catalog = catalog_of(document)
        changed = sum(_ensure_style(document, catalog, base, plan.spacing) for base in plan.needed)
        for paragraph in plan.direct:
            document.edit(Part.CONTENT)
            paragraph.set(qn("text", "style-name"), derived_style_name(_style_key(paragraph)))
            changed += 1
        if not changed:
            return (Outcome(self.name, Status.UNCHANGED, "Spacing already normalized."),)
        message = f"Normalized spacing to match reference style {plan.reference_style!r}."
        return (Outcome(self.name, Status.APPLIED, message, count=changed),)

    def _plan(self, document: OdfDocument) -> _Plan | tuple[Outcome, ...]:
        """Resolve the reference, the spacing and the affected paragraphs before any edit.

        Returns
        -------
        _Plan | tuple[Outcome, ...]
            The plan, or the failed outcome explaining why none can be made.

        """
        tree = document.tree(Part.CONTENT)
        reference = self._reference(tree)
        if reference is None:
            return (self._failed(f"Reference paragraph not found: {self.reference_text!r}"),)
        reference_style = paragraph_style_name(reference)
        spacing = catalog_of(document).spacing_signature(reference_style)
        if not spacing:
            return (self._failed(f"Reference style {reference_style!r} has no spacing to copy."),)
        clones = {derived_style_name(style): style for style in self.target_styles}
        if len(clones) != len(set(self.target_styles)):
            return (self._failed("Two target styles map to the same derived style name."),)
        paragraphs = text_nodes(
            tree,
            qn("text", "p"),
            *([qn("text", "h")] if self.include_headings else []),
            main_only=True,
        )
        direct = [p for p in paragraphs if _style_key(p) in self.target_styles]
        derived = [p for p in paragraphs if _style_key(p) in clones]
        for paragraph in [*direct, *derived]:
            paragraph_style_name(paragraph)
        if not direct and not derived:
            return (self._failed("No paragraph uses a target style."),)
        needed = sorted({_style_key(p) for p in direct} | {clones[_style_key(p)] for p in derived})
        plan = _Plan(reference_style, spacing, direct, needed)
        catalog = catalog_of(document)
        for base in needed:
            catalog.effective_paragraph_properties(None if base == NO_STYLE else base)
        conflicts = [
            message for base in needed if (message := _conflict(catalog, base)) is not None
        ]
        conflicts += _excluded_consumers(document, plan, set(direct) | set(derived))
        return tuple(self._failed(message) for message in conflicts) if conflicts else plan

    def _failed(self, message: str) -> Outcome:
        return Outcome(self.name, Status.FAILED, message)

    def _reference(self, tree: etree._ElementTree) -> etree._Element | None:
        for node in text_nodes(tree, qn("text", "p"), qn("text", "h"), main_only=True):
            current = element_text(node)
            if (
                (self.reference_text == current)
                if self.exact_reference
                else (self.reference_text in current)
            ):
                return node
        return None


@dataclass(frozen=True, slots=True)
class _Plan:
    reference_style: str | None
    spacing: dict[str, str]
    direct: list[etree._Element]
    needed: list[str]


def _conflict(catalog: StyleCatalog, base: str) -> str | None:
    name = derived_style_name(base)
    existing = catalog.style("paragraph", name)
    if existing is None or is_generated_from(
        catalog, existing, None if base == NO_STYLE else base, name
    ):
        return None
    return (
        f"A style named {name!r} already exists and is not an unmodified derivation of "
        f"{base!r} (another author's style, or the base style changed since); "
        "it is left untouched and spacing is not applied."
    )


def _ensure_style(
    document: OdfDocument, catalog: StyleCatalog, base: str, spacing: dict[str, str]
) -> int:
    name = derived_style_name(base)
    existing = catalog.style("paragraph", name)
    if existing is not None:
        if catalog.own_spacing(name) == spacing:
            return 0
        document.edit(Part.CONTENT)
        set_spacing(existing, spacing)
        return 1
    document.edit(Part.CONTENT)
    adopt_style(
        catalog,
        derive_paragraph_style(catalog, None if base == NO_STYLE else base, name, spacing),
    )
    return 1


def _style_key(paragraph: etree._Element) -> str:
    return paragraph.get(qn("text", "style-name")) or NO_STYLE


def _excluded_consumers(
    document: OdfDocument, plan: _Plan, selected: set[etree._Element]
) -> list[str]:
    catalog = catalog_of(document)
    changed = {
        derived_style_name(base)
        for base in plan.needed
        if catalog.own_spacing(derived_style_name(base)) != plan.spacing
    }
    if any(
        (node.get(qn("text", "style-name")) in changed and node not in selected)
        or any(
            changed.intersection(node.get(qn("text", name), "").split())
            for name in ("class-names", "cond-style-name")
        )
        for node in document.tree(Part.CONTENT).iter(qn("text", "p"), qn("text", "h"))
    ):
        return [
            (
                "A spacing style is shared with excluded content or other unselected "
                "or unestablished consumers; "
                "native editing is required."
            )
        ]
    return []
