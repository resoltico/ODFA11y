# SPDX-License-Identifier: MPL-2.0
"""Apply reviewed target-local language without rewriting text or shared styles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.content import protected_xml
from odfa11y.errors import RemediationError
from odfa11y.families.text.style_properties import paragraph_style_name
from odfa11y.families.text.styles import adopt_style, catalog_of
from odfa11y.language_tags import normalize_language
from odfa11y.odf import NS, Family, qn

from .effective import (
    BLOCKS,
    INLINE,
    effective_languages,
    effective_text_properties,
    language_targets,
    languages_from_properties,
)
from .styles import STYLE_NAME, binding_of, derive, family_of, normalized_language_tree

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lxml import etree

    from odfa11y.odf import OdfDocument

    from .styles import Binding


@dataclass(frozen=True, slots=True)
class TargetLanguage:
    """Explicit channel overrides bound to a reviewed paragraph or inline target."""

    western: str | None = None
    asian: str | None = None
    complex: str | None = None
    fingerprint: str | None = None


@dataclass(frozen=True)
class PreparedLanguage:
    """One fully checked style derivation, with no mutation performed yet."""

    target: str
    node: etree._Element
    binding: Binding
    style: etree._Element
    changed: bool


@dataclass(frozen=True, slots=True)
class SetTargetLanguages(Operation):
    """Preflight all target styles before applying any selected language override."""

    entries: Mapping[str, TargetLanguage]
    name: ClassVar[str] = "set_target_languages"
    families: ClassVar[frozenset[Family] | None] = frozenset({Family.TEXT})

    def prepare(self, document: OdfDocument) -> tuple[PreparedLanguage, ...]:
        """Resolve fingerprints, inheritance and style collisions before editing.

        Returns
        -------
        tuple[PreparedLanguage, ...]
            Checked target-specific derivations.

        Raises
        ------
        RemediationError
            Any target, declaration, fingerprint or definition is unresolved.

        """
        targets = language_targets(document)
        prepared = []
        for target, answer in self.entries.items():
            node = targets.get(target)
            if node is None or answer.fingerprint != language_fingerprint(document, node):
                message = "Language target or reviewed fingerprint no longer matches."
                raise RemediationError(message)
            prepared.append(_prepare(document, target, node, answer))
        return tuple(prepared)

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        try:
            prepared = self.prepare(document)
        except RemediationError as error:
            return (Outcome(self.name, Status.FAILED, str(error)),)
        catalog = catalog_of(document)
        outcomes = []
        for item in prepared:
            if item.changed:
                family = family_of(item.node)
                if catalog.style(family, item.binding.name) is None:
                    adopt_style(catalog, item.style)
                item.node.set(STYLE_NAME, item.binding.name)
            outcomes.append(
                Outcome(
                    self.name,
                    Status.APPLIED if item.changed else Status.UNCHANGED,
                    "Applied reviewed target language."
                    if item.changed
                    else "Target language already matches.",
                    key=item.target,
                    count=int(item.changed),
                )
            )
        return tuple(outcomes)


def _prepare(
    document: OdfDocument, target: str, node: etree._Element, answer: TargetLanguage
) -> PreparedLanguage:
    paragraph_style_name(node)
    old = binding_of(document, node, target)
    requested = (answer.western, answer.asian, answer.complex)
    if not any(value is not None for value in requested):
        message = "Select at least one target language channel."
        raise RemediationError(message)
    effective = effective_languages(document, node)
    overrides = list(old.overrides)
    for index, tag in enumerate(requested):
        if tag is not None:
            if not isinstance(tag, str):
                message = "Target language must be a valid language tag."
                raise RemediationError(message)
            try:
                overrides[index] = normalize_language(tag)
            except ValueError as error:
                raise RemediationError(str(error)) from error
    binding = replace(old, overrides=tuple(overrides))
    style = derive(document, family_of(node), binding)
    existing = catalog_of(document).style(family_of(node), binding.name)
    if existing is not None and protected_xml(existing) != protected_xml(style):
        message = "Generated language style name belongs to a different definition."
        raise RemediationError(message)
    _require_effective_override(document, node, binding, style)
    changed = any(
        tag is not None and effective[index] != overrides[index]
        for index, tag in enumerate(requested)
    )
    return PreparedLanguage(target, node, binding, style, changed)


def _require_effective_override(
    document: OdfDocument, node: etree._Element, binding: Binding, style: etree._Element
) -> None:
    catalog = catalog_of(document)
    family = family_of(node)
    chain = catalog.inheritance_chain(family, binding.base)
    parent = chain[-1].get(qn("style", "parent-style-name")) if chain else None
    container = node.getparent()
    props = (
        effective_text_properties(document, container)
        if node.tag in INLINE and container is not None
        else {}
    )
    props.update(catalog.effective_properties(family, parent, "text-properties"))
    properties = style.find("style:text-properties", NS)
    if properties is not None:
        props.update(properties.attrib)
    resolved = languages_from_properties(props)
    if any(
        tag is not None and tag != resolved[index] for index, tag in enumerate(binding.overrides)
    ):
        message = (
            "Inherited full language tag prevents this override; "
            "edit the target language in Writer."
        )
        raise RemediationError(message)


def language_fingerprint(document: OdfDocument, node: etree._Element) -> str:
    """Bind authored content and original style definitions independently of our overrides.

    Returns
    -------
    str
        Sixteen lowercase hexadecimal characters, stable after verified language edits.

    """
    targets = {node: target for target, node in language_targets(document).items()}
    catalog = catalog_of(document)
    styles = []
    for styled in reversed([node, *node.iterancestors()]):
        if styled.tag not in BLOCKS | INLINE:
            continue
        binding = binding_of(document, styled, targets[styled])
        family = family_of(styled)
        styles.append([
            catalog.effective_properties(family, binding.base, "text-properties"),
            catalog.effective_properties(family, binding.base, "paragraph-properties"),
            [protected_xml(style) for style in catalog.inheritance_chain(family, binding.base)],
        ])
    content = protected_xml(normalized_language_tree(document, node))
    return hashlib.sha256(json.dumps([content, styles], sort_keys=True).encode()).hexdigest()[:16]
