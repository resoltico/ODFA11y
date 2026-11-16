# SPDX-License-Identifier: AGPL-3.0-only
"""Apply reviewed target-local language without rewriting text or shared styles."""

import json
from dataclasses import dataclass, replace

lazy from lxml import etree

from odfa11y.concepts import protected_xml
from odfa11y.decisions import Decision
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import EditResult, Outcome, Status
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.answers import TargetLanguageAnswer
from odfa11y.families.text.language.effective import (
    BLOCKS,
    INLINE,
    effective_languages,
    effective_text_properties,
    language_targets,
    languages_from_properties,
)
from odfa11y.families.text.language.styles import (
    STYLE_NAME,
    binding_of,
    derive,
    family_of,
    language_normalization,
)
from odfa11y.families.text.styles.properties import paragraph_style_name
from odfa11y.language_tags import normalize_language
from odfa11y.odf import NS, Part
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import Allowance, Attributes, Created
from odfa11y.odf.styles import adopt_style, normalize_generated, styles_of
from odfa11y.targets import Fingerprint, TargetPath
lazy from odfa11y.families.text.language.styles import Binding
lazy from odfa11y.odf import OdfDocument


@dataclass(frozen=True)
class PreparedLanguage:
    """One fully checked style derivation, with no mutation performed yet."""

    target: TargetPath
    node: etree._Element
    binding: Binding
    style: etree._Element
    changed: bool


def _require_effective_override(
    document: OdfDocument, node: etree._Element, binding: Binding, style: etree._Element
) -> None:
    catalog = styles_of(document)
    family = family_of(node)
    chain = catalog.chain(family, binding.base)
    parent = chain[-1].get(xml_names.STYLE_PARENT_STYLE_NAME) if chain else None
    container = node.getparent()
    props = (
        effective_text_properties(document, container)
        if node.tag in INLINE and container is not None
        else {}
    )
    props.update(catalog.effective(family, parent, "text-properties"))
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
        raise DocumentRefusal(message)


def language_fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    """Bind authored content and original style definitions independently of our overrides.

    Returns
    -------
    str
        Sixteen lowercase hexadecimal characters, stable after verified language edits.

    """
    targets = {node: target for target, node in language_targets(document).items()}
    catalog = styles_of(document)
    styles = []
    for styled in reversed([node, *node.iterancestors()]):
        if styled.tag not in BLOCKS | INLINE:
            continue
        binding = binding_of(document, styled, targets[styled])
        family = family_of(styled)
        styles.append([
            catalog.effective(family, binding.base, "text-properties"),
            catalog.effective(family, binding.base, "paragraph-properties"),
            [protected_xml(style) for style in catalog.chain(family, binding.base)],
        ])
    content = protected_xml(normalize_generated(node, language_normalization(document)))
    return Fingerprint.of(json.dumps([content, styles], sort_keys=True).encode())


def _prepare_answer(
    document: OdfDocument, target: TargetPath, node: etree._Element, answer: TargetLanguageAnswer
) -> PreparedLanguage:
    paragraph_style_name(node)
    old = binding_of(document, node, target)
    requested = (answer.western, answer.asian, answer.complex)
    effective = effective_languages(document, node)
    overrides = list(old.overrides)
    for index, tag in enumerate(requested):
        if tag is not None:
            overrides[index] = normalize_language(tag)
    binding = replace(old, overrides=tuple(overrides))
    style = derive(document, family_of(node), binding)
    existing = styles_of(document).resolve(family_of(node), binding.name)
    if existing is not None and protected_xml(existing) != protected_xml(style):
        message = "Generated language style name belongs to a different definition."
        raise DocumentRefusal(message)
    _require_effective_override(document, node, binding, style)
    changed = any(
        tag is not None and effective[index] != overrides[index]
        for index, tag in enumerate(requested)
    )
    return PreparedLanguage(target, node, binding, style, changed)


def prepare_language(
    document: OdfDocument, decision: Decision[TargetLanguageAnswer]
) -> PreparedLanguage:
    """Establish the target's derivation and collision safeguards before changing any style."""
    node = resolved_node(document, decision)
    return _prepare_answer(document, decision.target_path, node, decision.answer)


def edit_language(document: OdfDocument, decision: Decision[TargetLanguageAnswer]) -> EditResult:
    """Apply explicit language channels without changing authored text or shared styles."""
    item = prepare_language(document, decision)
    allowance = Allowance()
    expected = protected_xml(item.style)
    catalog = styles_of(document)
    if item.changed:
        family = family_of(item.node)
        if catalog.resolve(family, item.binding.name) is None:
            created = adopt_style(catalog, item.style)
            # Preserve Q19's pre-adoption namespace-sensitive creation receipt.
            allowance = Allowance(
                tuple(
                    replace(permission, expected=expected)
                    if isinstance(permission, Created) and permission.node is item.style
                    else permission
                    for permission in created.permissions
                )
            )
        allowance |= Allowance((Attributes(Part.CONTENT, item.node, frozenset({STYLE_NAME})),))
        item.node.set(STYLE_NAME, item.binding.name)
    return EditResult(
        (
            Outcome(
                decision.kind.id,
                Status.APPLIED if item.changed else Status.UNCHANGED,
                "Applied reviewed target language."
                if item.changed
                else "Target language already matches.",
                target=item.target,
                count=int(item.changed),
            ),
        ),
        allowance,
    )
