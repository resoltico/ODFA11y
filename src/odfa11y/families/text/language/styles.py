# SPDX-License-Identifier: AGPL-3.0-only
"""Derive and independently recognize target-local language styles."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated

from lxml import etree

from odfa11y.concepts import CHANNEL_ATTRIBUTES
from odfa11y.contracts import ItemCount, LanguageTag
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.language.effective import BLOCKS, CHANNELS, language_targets
from odfa11y.language_tags import language_parts, normalize_language
from odfa11y.odf import NS
from odfa11y.odf import names as xml_names
from odfa11y.odf.styles import (
    GeneratedStyle,
    StyleNormalization,
    generated_binding,
    generated_name,
    generated_prefix,
    styles_of,
)
from odfa11y.targets import TargetPath
lazy from odfa11y.odf import OdfDocument

PREFIX = generated_prefix("language")
STYLE_NAME = xml_names.TEXT_STYLE_NAME


@dataclass(frozen=True)
class Binding:
    """Original style identity plus explicit target-local channel overrides."""

    base: str | None
    overrides: Annotated[
        tuple[Annotated[str | None, LanguageTag()], ...], ItemCount(minimum=3, maximum=3)
    ]
    target: TargetPath

    @property
    def name(self) -> str:
        """Encode the derivation inputs in a legal, independently verifiable style name."""
        return generated_name("language", self)


def family_of(node: etree._Element) -> str:
    """Select the ODF family governing the target's style reference.

    Returns
    -------
    str
        Paragraph for blocks, text for inline targets.

    """
    return "paragraph" if node.tag in BLOCKS else "text"


def derive(document: OdfDocument, family: str, binding: Binding) -> etree._Element:
    """Clone the authored style and change only the explicitly selected channels.

    Returns
    -------
    etree._Element
        A detached automatic style; its authored base remains untouched.

    Raises
    ------
    DocumentRefusal
        The original style cannot be uniquely resolved.

    """
    catalog = styles_of(document)
    base = catalog.resolve(family, binding.base)
    if binding.base and base is None:
        message = "The original language style is missing."
        raise DocumentRefusal(message)
    style = catalog.derive(family, base, purpose="language", binding=binding).element
    props = style.find("style:text-properties", NS)
    if props is None:
        props = etree.SubElement(style, xml_names.STYLE_TEXT_PROPERTIES)
    for channel, tag in enumerate(binding.overrides):
        if tag is None:
            continue
        for key, value in zip(CHANNEL_ATTRIBUTES[channel], language_parts(tag), strict=True):
            props.attrib.pop(key, None)
            if value is not None:
                props.set(key, value)
    return style


def binding_of(document: OdfDocument, node: etree._Element, target: TargetPath) -> Binding:
    """Prove any generated derivation before recovering its original style identity.

    Returns
    -------
    Binding
        Verified prior overrides, or an unmodified authored base.

    Raises
    ------
    DocumentRefusal
        A generated-looking name or definition does not prove this target's derivation.

    """
    name = node.get(STYLE_NAME)
    if not name or not name.startswith(PREFIX):
        return Binding(name, (None, None, None), target)
    message = "Target language style is not a verified derivation; review it in Writer."
    try:
        binding = _decode(name, target)
    except DocumentRefusal as error:
        raise DocumentRefusal(message) from error
    actual = styles_of(document).resolve(family_of(node), name)
    if actual is None:
        raise DocumentRefusal(message)
    parent = actual.getparent()
    expected = derive(document, family_of(node), binding)
    if parent is None or parent.tag != xml_names.OFFICE_AUTOMATIC_STYLES:
        raise DocumentRefusal(message)
    if not styles_of(document).is_generated(actual, GeneratedStyle(binding.name, expected)):
        raise DocumentRefusal(message)
    return binding


def _decode(name: str, target: TargetPath) -> Binding:
    value = generated_binding(name, "language", Binding)
    if value.base is not None and value.base.startswith(PREFIX):
        message = "Language derivations cannot recursively bind another language derivation."
        raise DocumentRefusal(message)
    if value.target != target or len(value.overrides) != len(CHANNELS):
        message = "Language derivation does not match this target."
        raise DocumentRefusal(message)
    normalized = tuple(
        normalize_language(tag) if tag is not None else None for tag in value.overrides
    )
    binding = Binding(value.base, normalized, target)
    if binding.name != name:
        message = "Language derivation values are not canonical."
        raise DocumentRefusal(message)
    return binding


def language_normalization(document: OdfDocument) -> StyleNormalization:
    targets = {node: target for target, node in language_targets(document).items()}

    def restore(
        source: etree._Element, current: Mapping[str, str]
    ) -> Mapping[str, str | None] | None:
        name = current.get(STYLE_NAME, "")
        if source not in targets or not name.startswith(PREFIX):
            return None
        try:
            binding = binding_of(document, source, targets[source])
        except DocumentRefusal:
            return None
        return {STYLE_NAME: binding.base}

    return StyleNormalization((STYLE_NAME,), restore)
