# SPDX-License-Identifier: MPL-2.0
"""Apply and verify paragraph spacing through isolated derived styles."""

from collections.abc import Mapping
from dataclasses import dataclass

lazy from lxml import etree

from odfa11y.concepts import eligible_text_node, visible_words
from odfa11y.decisions import Decision
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal, XmlParseError
from odfa11y.families.text.answers import TextSpacingAnswer
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.styles.properties import paragraph_style_name
from odfa11y.odf import Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.odf.styles import (
    NO_STYLE,
    StyleNormalization,
    adopt_style,
    derive_paragraph_style,
    derived_style_name,
    is_generated_from,
    set_spacing,
    styles_of,
)
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.odf.styles import StyleResolver


@dataclass(frozen=True, slots=True)
class _Plan:
    reference_style: str | None
    spacing: dict[str, str]
    direct: list[etree._Element]
    needed: list[str]


def _conflict(catalog: StyleResolver, base: str) -> str | None:
    name = derived_style_name(base)
    existing = catalog.resolve("paragraph", name)
    if existing is None or is_generated_from(
        catalog, existing, None if base == NO_STYLE else base, name
    ):
        return None
    return (
        f"A style named {name!r} already exists and is not an unmodified derivation of "
        f"{base!r} (another author's style, or the base style changed since); "
        "it is left untouched and spacing is not applied."
    )


def _ensure_style(catalog: StyleResolver, base: str, spacing: dict[str, str]) -> int:
    name = derived_style_name(base)
    existing = catalog.resolve("paragraph", name)
    if existing is not None:
        if catalog.own_spacing(name) == spacing:
            return 0
        set_spacing(existing, spacing)
        return 1
    adopt_style(
        catalog,
        derive_paragraph_style(catalog, None if base == NO_STYLE else base, name, spacing),
    )
    return 1


def _style_key(paragraph: etree._Element) -> str:
    return paragraph.get(xml_names.TEXT_STYLE_NAME) or NO_STYLE


def _excluded_consumers(
    document: OdfDocument, plan: _Plan, selected: set[etree._Element]
) -> list[str]:
    catalog = styles_of(document)
    changed = {
        derived_style_name(base)
        for base in plan.needed
        if catalog.own_spacing(derived_style_name(base)) != plan.spacing
    }
    if any(
        (node.get(xml_names.TEXT_STYLE_NAME) in changed and node not in selected)
        or any(
            changed.intersection(node.get(qn("text", name), "").split())
            for name in ("class-names", "cond-style-name")
        )
        for node in document.tree(Part.CONTENT).iter(xml_names.TEXT_P, xml_names.TEXT_H)
    ):
        return [
            (
                "A spacing style is shared with excluded content or other unselected "
                "or unestablished consumers; "
                "native editing is required."
            )
        ]
    return []


def spacing_normalization(document: OdfDocument) -> StyleNormalization:
    try:
        used = {
            style.get(xml_names.STYLE_NAME) for style in styles_of(document).styles("paragraph")
        }
        proven = _proven_references(document, used)
    except DocumentRefusal, XmlParseError:
        proven = {}

    def restore(
        source: etree._Element, current: Mapping[str, str]
    ) -> Mapping[str, str | None] | None:
        if source.tag not in {xml_names.TEXT_P, xml_names.TEXT_H} or not eligible_text_node(
            source, main_only=True
        ):
            return None
        if any(qn("text", name) in source.attrib for name in ("class-names", "cond-style-name")):
            return None
        name = current.get(xml_names.TEXT_STYLE_NAME)
        if name is None or name not in proven:
            return None
        base = proven[name]
        return {xml_names.TEXT_STYLE_NAME: None if base == NO_STYLE else base}

    return StyleNormalization((xml_names.TEXT_STYLE_NAME,), restore)


def _proven_references(document: OdfDocument, used: set[str | None]) -> dict[str, str]:
    catalog = styles_of(document)
    bases = {
        NO_STYLE,
        *(style.get(xml_names.STYLE_NAME, "") for style in catalog.styles("paragraph")),
    }
    proven = {}
    for base in bases:
        name = derived_style_name(base)
        if name not in used:
            continue
        style = catalog.resolve("paragraph", name)
        if style is not None and is_generated_from(
            catalog, style, None if base == NO_STYLE else base, name
        ):
            proven[name] = base
    return proven


@dataclass(frozen=True, slots=True)
class _SpacingEdit:
    """Give paragraphs of the target styles the effective spacing of a reference paragraph.

    Spacing is copied onto a derived style named after its base style and a digest of that
    name (``ODFA11y_spacing_<style>_<digest>``). A style of that name is reused only when it is
    provably our own earlier output; ODFA11y never overwrites or reinterprets another style.
    """

    decision: Decision[TextSpacingAnswer]

    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        try:
            plan = self._plan(document)
        except DocumentRefusal as exc:
            return (self._failed(str(exc)),)
        if isinstance(plan, tuple):
            return plan
        catalog = styles_of(document)
        changed = sum(_ensure_style(catalog, base, plan.spacing) for base in plan.needed)
        for paragraph in plan.direct:
            paragraph.set(xml_names.TEXT_STYLE_NAME, derived_style_name(_style_key(paragraph)))
            changed += 1
        if not changed:
            return (
                Outcome(self.decision.kind.id, Status.UNCHANGED, "Spacing already normalized."),
            )
        message = f"Normalized spacing to match reference style {plan.reference_style!r}."
        return (Outcome(self.decision.kind.id, Status.APPLIED, message, count=changed),)

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
            return (
                self._failed(
                    f"Reference paragraph not found: {self.decision.answer.reference_text!r}"
                ),
            )
        reference_style = paragraph_style_name(reference)
        spacing = styles_of(document).spacing_signature(reference_style)
        if not spacing:
            return (self._failed(f"Reference style {reference_style!r} has no spacing to copy."),)
        clones = {derived_style_name(style): style for style in self.decision.answer.target_styles}
        if len(clones) != len(set(self.decision.answer.target_styles)):
            return (self._failed("Two target styles map to the same derived style name."),)
        paragraphs = text_nodes(
            tree,
            xml_names.TEXT_P,
            *([xml_names.TEXT_H] if self.decision.answer.include_headings else []),
            main_only=True,
        )
        direct = [p for p in paragraphs if _style_key(p) in self.decision.answer.target_styles]
        derived = [p for p in paragraphs if _style_key(p) in clones]
        for paragraph in [*direct, *derived]:
            paragraph_style_name(paragraph)
        if not direct and not derived:
            return (self._failed("No paragraph uses a target style."),)
        needed = sorted({_style_key(p) for p in direct} | {clones[_style_key(p)] for p in derived})
        plan = _Plan(reference_style, spacing, direct, needed)
        catalog = styles_of(document)
        for base in needed:
            catalog.effective_paragraph_properties(None if base == NO_STYLE else base)
        conflicts = [
            message for base in needed if (message := _conflict(catalog, base)) is not None
        ]
        conflicts += _excluded_consumers(document, plan, set(direct) | set(derived))
        return tuple(self._failed(message) for message in conflicts) if conflicts else plan

    def _failed(self, message: str) -> Outcome:
        return Outcome(self.decision.kind.id, Status.FAILED, message)

    def _reference(self, tree: etree._ElementTree) -> etree._Element | None:
        for node in text_nodes(tree, xml_names.TEXT_P, xml_names.TEXT_H, main_only=True):
            current = visible_words(node)
            if (
                (self.decision.answer.reference_text == current)
                if self.decision.answer.exact_reference
                else (self.decision.answer.reference_text in current)
            ):
                return node
        return None


def edit_spacing(
    document: OdfDocument, decision: Decision[TextSpacingAnswer]
) -> tuple[Outcome, ...]:
    """Normalize only the reviewed paragraph styles using established derived-style guards."""
    return _SpacingEdit(decision).apply(document)
