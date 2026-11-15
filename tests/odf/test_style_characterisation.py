# SPDX-License-Identifier: MPL-2.0
"""Pin legal scopes and provenance at all four style call sites before consolidation."""

from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree

from odfa11y.concepts import protected_xml
from odfa11y.concepts.graphic_styles import (
    GraphicRoleEditor,
    GraphicRoles,
    graphic_normalization,
)
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.language.effective import language_targets
from odfa11y.families.text.language.styles import (
    Binding,
    binding_of,
    derive,
    language_normalization,
)
from odfa11y.odf import NS, OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.odf.styles import (
    adopt_style,
    derive_paragraph_style,
    derived_style_name,
    is_generated_from,
    normalize_generated,
    styles_of,
)
from odfa11y.targets import TargetPath
from tests.fixtures.graphics import _style as graphic_style
from tests.fixtures.writer import make_minimal_odt


def _document(tmp_path: Path) -> OdfDocument:
    return OdfDocument.open(
        make_minimal_odt(tmp_path / "source.odt", features={"with_image_without_alt": True})
    )


def _style(
    parent: etree._Element, family: str, name: str, *, base: str | None = None
) -> etree._Element:
    style = etree.SubElement(
        parent, xml_names.STYLE_STYLE, {xml_names.STYLE_FAMILY: family, xml_names.STYLE_NAME: name}
    )
    if base is not None:
        style.set(xml_names.STYLE_PARENT_STYLE_NAME, base)
    return style


def test_paragraph_automatic_styles_shadow_common_names_and_inherit_common_parents(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path)
    common_scope = document.tree(Part.STYLES).find("office:styles", NS)
    automatic_scope = document.tree(Part.CONTENT).find("office:automatic-styles", NS)
    assert common_scope is not None
    assert automatic_scope is not None
    common = _style(common_scope, "paragraph", "Shared")
    etree.SubElement(
        common, xml_names.STYLE_PARAGRAPH_PROPERTIES, {xml_names.FO_MARGIN_TOP: "0.2cm"}
    )
    automatic = _style(automatic_scope, "paragraph", "Shared", base="Shared")
    etree.SubElement(
        automatic, xml_names.STYLE_PARAGRAPH_PROPERTIES, {xml_names.FO_MARGIN_BOTTOM: "0.8cm"}
    )
    catalog = styles_of(document)
    assert catalog.resolve("paragraph", "Shared") is automatic
    assert catalog.resolve("paragraph", "Shared", common=True) is common
    assert catalog.chain("paragraph", "Shared") == [common, automatic]
    properties = catalog.effective_paragraph_properties("Shared")
    assert properties[xml_names.FO_MARGIN_TOP] == "0.2cm"
    assert properties[xml_names.FO_MARGIN_BOTTOM] == "0.8cm"
    common_scope.append(deepcopy(common))
    document.checkpoint()
    with pytest.raises(DocumentRefusal, match="ambiguous"):
        styles_of(document).chain("paragraph", "Shared")


def test_graphic_role_inheritance_respects_the_same_two_legal_scopes(tmp_path: Path) -> None:
    document = _document(tmp_path)
    common_scope = document.tree(Part.STYLES).find("office:styles", NS)
    automatic_scope = document.tree(Part.CONTENT).find("office:automatic-styles", NS)
    assert common_scope is not None
    assert automatic_scope is not None
    common = _style(common_scope, "graphic", "Shared")
    etree.SubElement(
        common, xml_names.STYLE_GRAPHIC_PROPERTIES, {xml_names.DRAW_DECORATIVE: "true"}
    )
    automatic = _style(automatic_scope, "graphic", "Shared", base="Shared")
    styles = GraphicRoles(document)
    assert styles.resolve("graphic", "Shared") is automatic
    assert styles.resolve("graphic", "Shared", common=True) is common
    assert styles.chain_role(automatic, "graphic") == "true"
    etree.SubElement(
        automatic, xml_names.STYLE_GRAPHIC_PROPERTIES, {xml_names.DRAW_DECORATIVE: "false"}
    )
    assert GraphicRoles(document).chain_role(automatic, "graphic") == "false"
    common_scope.append(deepcopy(common))
    with pytest.raises(DocumentRefusal, match="ambiguous"):
        GraphicRoles(document).chain_role(automatic, "graphic")


def test_spacing_provenance_accepts_only_the_declared_change_and_content_scope(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path)
    catalog = styles_of(document)
    base = catalog.resolve("paragraph", "Body")
    assert base is not None
    before = protected_xml(base)
    name = derived_style_name("Body")
    generated = derive_paragraph_style(catalog, "Body", name, {"fo:margin-top": "0.8cm"})
    adopt_style(catalog, generated)
    assert is_generated_from(catalog, generated, "Body", name)
    properties = generated.find("style:paragraph-properties", NS)
    assert properties is not None
    properties.set(xml_names.FO_KEEP_WITH_NEXT, "always")
    assert not is_generated_from(catalog, generated, "Body", name)
    assert protected_xml(base) == before


def test_language_provenance_is_target_bound_and_preserves_nonlanguage_properties(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path)
    node = next(document.tree(Part.CONTENT).iter(xml_names.TEXT_P))
    node.set(xml_names.TEXT_STYLE_NAME, "Body")
    target = next(
        path for path, candidate in language_targets(document).items() if candidate is node
    )
    binding = Binding("Body", ("de-DE", None, None), target)
    generated = derive(document, "paragraph", binding)
    adopt_style(styles_of(document), generated)
    node.set(xml_names.TEXT_STYLE_NAME, binding.name)
    assert binding_of(document, node, binding.target) == binding
    clone = normalize_generated(node, language_normalization(document))
    assert clone.get(xml_names.TEXT_STYLE_NAME) == "Body"
    with pytest.raises(DocumentRefusal, match="verified derivation"):
        binding_of(document, node, TargetPath("content/language[999]"))
    properties = generated.find("style:text-properties", NS)
    assert properties is not None
    properties.set(xml_names.FO_FONT_WEIGHT, "bold")
    with pytest.raises(DocumentRefusal, match="verified derivation"):
        binding_of(document, node, binding.target)


def test_graphic_role_provenance_restores_only_a_verified_reference(tmp_path: Path) -> None:
    document = _document(tmp_path)
    frame = next(document.tree(Part.CONTENT).iter(xml_names.DRAW_FRAME))
    graphic_style(document, "Visual", role="false")
    frame.set(xml_names.DRAW_STYLE_NAME, "Visual")
    original = frame.get(xml_names.DRAW_STYLE_NAME)
    assert GraphicRoleEditor(document).set_role(frame, decorative=True)
    name = frame.get(xml_names.DRAW_STYLE_NAME)
    assert name
    assert name != original
    assert (
        normalize_generated(frame, graphic_normalization(document)).get(xml_names.DRAW_STYLE_NAME)
        == original
    )
    styles = document.tree(Part.CONTENT).find("office:automatic-styles", NS)
    assert styles is not None
    generated = next(style for style in styles if style.get(xml_names.STYLE_NAME) == name)
    properties = generated.find("style:graphic-properties", NS)
    assert properties is not None
    properties.set(xml_names.DRAW_FILL_COLOR, "#ff0000")
    assert (
        normalize_generated(frame, graphic_normalization(document)).get(xml_names.DRAW_STYLE_NAME)
        == name
    )
