# SPDX-License-Identifier: MPL-2.0
"""Copy a reference paragraph style's spacing onto selected paragraph styles."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import Family, Part, qn, select_elements

from .derived_styles import adopt_style, derive_paragraph_style, is_generated_from, set_spacing
from .styles import catalog_of

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

    from .styles import StyleCatalog

NO_STYLE = "(none)"
SAFE_NAME_LENGTH = 32
NAME_DIGEST_LENGTH = 8


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
        plan = self._plan(document)
        if isinstance(plan, tuple):
            return plan
        catalog = catalog_of(document)
        conflicts = [
            message for base in plan.needed if (message := _conflict(catalog, base)) is not None
        ]
        if conflicts:
            return tuple(self._failed(message) for message in conflicts)
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
        reference_style = reference.get(qn("text", "style-name"))
        spacing = catalog_of(document).spacing_signature(reference_style)
        if not spacing:
            return (self._failed(f"Reference style {reference_style!r} has no spacing to copy."),)
        clones = {derived_style_name(style): style for style in self.target_styles}
        if len(clones) != len(set(self.target_styles)):
            return (self._failed("Two target styles map to the same derived style name."),)
        selector = "//text:p" + (" | //text:h" if self.include_headings else "")
        paragraphs = select_elements(tree, selector)
        direct = [p for p in paragraphs if _style_key(p) in self.target_styles]
        derived = [p for p in paragraphs if _style_key(p) in clones]
        if not direct and not derived:
            return (self._failed("No paragraph uses a target style."),)
        needed = sorted({_style_key(p) for p in direct} | {clones[_style_key(p)] for p in derived})
        return _Plan(reference_style, spacing, direct, needed)

    def _failed(self, message: str) -> Outcome:
        return Outcome(self.name, Status.FAILED, message)

    def _reference(self, tree: etree._ElementTree) -> etree._Element | None:
        for node in select_elements(tree, "//text:p | //text:h"):
            current = "".join(node.itertext()).strip()
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


def derived_style_name(base: str) -> str:
    """Name the derived style that carries normalized spacing for a base style.

    The digest of the full base name keeps two bases that sanitise to the same text apart
    and keeps the name out of the way of styles an author is likely to choose.

    Returns
    -------
    str
        A deterministic style name containing only letters, digits and underscores.

    """
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_")[:SAFE_NAME_LENGTH] or "Body"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:NAME_DIGEST_LENGTH]
    return f"A11ySpacing_{safe}_{digest}"


def _style_key(paragraph: etree._Element) -> str:
    return paragraph.get(qn("text", "style-name")) or NO_STYLE
