# SPDX-License-Identifier: MPL-2.0
"""Derive and independently recognize target-local language styles."""

from __future__ import annotations

import base64
import binascii
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.content import CHANNEL_ATTRIBUTES, protected_xml
from odfa11y.errors import RemediationError
from odfa11y.families.text.styles import catalog_of
from odfa11y.language_tags import language_parts, normalize_language
from odfa11y.odf import NS, qn

from .effective import BLOCKS, CHANNELS, language_targets

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

PREFIX = "A11yLanguage_"
STYLE_NAME = qn("text", "style-name")


@dataclass(frozen=True)
class Binding:
    """Original style identity plus explicit target-local channel overrides."""

    base: str | None
    overrides: tuple[str | None, ...]
    target: str

    @property
    def name(self) -> str:
        """Encode the derivation inputs in a legal, independently verifiable style name."""
        payload = json.dumps([self.base, self.overrides, self.target], separators=(",", ":"))
        return PREFIX + base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


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
    RemediationError
        The original style cannot be uniquely resolved.

    """
    catalog = catalog_of(document)
    base = catalog.style(family, binding.base)
    if binding.base and base is None:
        message = "The original language style is missing."
        raise RemediationError(message)
    style = deepcopy(base) if base is not None else etree.Element(qn("style", "style"))
    style.set(qn("style", "name"), binding.name)
    style.set(qn("style", "family"), family)
    props = style.find("style:text-properties", NS)
    if props is None:
        props = etree.SubElement(style, qn("style", "text-properties"))
    for channel, tag in enumerate(binding.overrides):
        if tag is None:
            continue
        for key, value in zip(CHANNEL_ATTRIBUTES[channel], language_parts(tag), strict=True):
            props.attrib.pop(key, None)
            if value is not None:
                props.set(key, value)
    return style


def binding_of(document: OdfDocument, node: etree._Element, target: str) -> Binding:
    """Prove any generated derivation before recovering its original style identity.

    Returns
    -------
    Binding
        Verified prior overrides, or an unmodified authored base.

    Raises
    ------
    RemediationError
        A generated-looking name or definition does not prove this target's derivation.

    """
    name = node.get(STYLE_NAME)
    if not name or not name.startswith(PREFIX):
        return Binding(name, (None, None, None), target)
    message = "Target language style is not a verified derivation; review it in Writer."
    try:
        binding = _decode(name, target)
    except (ValueError, TypeError, UnicodeError, binascii.Error) as error:
        raise RemediationError(message) from error
    actual = catalog_of(document).style(family_of(node), name)
    if actual is None:
        raise RemediationError(message)
    parent = actual.getparent()
    expected = derive(document, family_of(node), binding)
    if parent is None or parent.tag != qn("office", "automatic-styles"):
        raise RemediationError(message)
    if protected_xml(actual) != protected_xml(expected):
        raise RemediationError(message)
    return binding


def _decode(name: str, target: str) -> Binding:
    payload = name[len(PREFIX) :]
    base, overrides, bound_target = json.loads(
        base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True)
    )
    if base is not None and (not isinstance(base, str) or base.startswith(PREFIX)):
        raise ValueError
    if not isinstance(overrides, list) or len(overrides) != len(CHANNELS):
        raise ValueError
    if bound_target != target or any(
        tag is not None and not isinstance(tag, str) for tag in overrides
    ):
        raise ValueError
    normalized = tuple(normalize_language(tag) if tag is not None else None for tag in overrides)
    binding = Binding(base, normalized, target)
    if binding.name != name:
        raise ValueError
    return binding


def normalized_language_tree(document: OdfDocument, root: etree._Element) -> etree._Element:
    """Restore only independently proven language-style references in a copy.

    Returns
    -------
    etree._Element
        Authored references retained for unproven or excluded-context definitions.

    """
    clone = deepcopy(root)
    targets = {node: target for target, node in language_targets(document).items()}
    for source, target in zip(root.iter(), clone.iter(), strict=True):
        name = source.get(STYLE_NAME, "")
        if source not in targets or not name.startswith(PREFIX):
            continue
        try:
            binding = binding_of(document, source, targets[source])
        except RemediationError:
            continue
        target.attrib.pop(STYLE_NAME, None)
        if binding.base is not None:
            target.set(STYLE_NAME, binding.base)
    return clone
