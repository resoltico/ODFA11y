# SPDX-License-Identifier: MPL-2.0
"""Copy a reference paragraph style's spacing onto selected paragraph styles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.odf import qn, select_elements

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdtDocument

NO_STYLE = "(none)"


@dataclass(frozen=True, slots=True)
class NormalizeSpacing(Operation):
    """Give paragraphs of the target styles the effective spacing of a reference paragraph.

    Spacing is copied onto a deterministic derived style (``A11ySpacing_<style>``), so
    shared base styles are not rewritten and a repeated run recognises its own result.
    """

    reference_text: str
    target_styles: tuple[str, ...]
    exact_reference: bool = False
    include_headings: bool = False
    name: ClassVar[str] = "normalize_spacing"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        tree = document.tree("content.xml")
        catalog = document.catalog
        reference = self._reference(tree)
        if reference is None:
            return (self._failed(f"Reference paragraph not found: {self.reference_text!r}"),)
        reference_style = reference.get(qn("text", "style-name"))
        spacing = catalog.spacing_signature(reference_style)
        if not spacing:
            return (self._failed(f"Reference style {reference_style!r} has no spacing to copy."),)
        clones = {clone_style_name(style): style for style in self.target_styles}
        if len(clones) != len(set(self.target_styles)):
            return (self._failed("Two target styles map to the same derived style name."),)
        selector = "//text:p" + (" | //text:h" if self.include_headings else "")
        paragraphs = select_elements(tree, selector)
        direct = [p for p in paragraphs if _style_key(p) in self.target_styles]
        derived = [p for p in paragraphs if _style_key(p) in clones]
        if not direct and not derived:
            return (self._failed("No paragraph uses a target style."),)
        needed = {_style_key(p) for p in direct} | {clones[_style_key(p)] for p in derived}
        changed = 0
        for base in sorted(needed):
            clone = clone_style_name(base)
            if (
                catalog.style("paragraph", clone) is not None
                and catalog.own_spacing(clone) == spacing
            ):
                continue
            document.edit("content.xml")
            catalog.clone_paragraph_style_with_spacing(
                base_style_name=None if base == NO_STYLE else base,
                new_style_name=clone,
                spacing=spacing,
            )
            changed += 1
        for paragraph in direct:
            document.edit("content.xml")
            paragraph.set(qn("text", "style-name"), clone_style_name(_style_key(paragraph)))
            changed += 1
        if not changed:
            return (Outcome(self.name, Status.UNCHANGED, "Spacing already normalized."),)
        message = f"Normalized spacing to match reference style {reference_style!r}."
        return (Outcome(self.name, Status.APPLIED, message, count=changed),)

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


def clone_style_name(base: str) -> str:
    """Name the derived style that carries normalized spacing for a base style.

    Returns
    -------
    str
        A deterministic style name containing only letters, digits and underscores.

    """
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_")[:48] or "Body"
    return f"A11ySpacing_{safe}"


def _style_key(paragraph: etree._Element) -> str:
    return paragraph.get(qn("text", "style-name")) or NO_STYLE
