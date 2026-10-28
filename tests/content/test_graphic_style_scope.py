# SPDX-License-Identifier: MPL-2.0
"""Only legal applicable style containers can establish graphic roles."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.content import effective_graphic_role, normalized_role_attributes
from odfa11y.content.graphic_styles import GraphicRoleEditor, GraphicStyles
from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.source_audit import audit_odf
from tests.content.test_graphic_roles_links import _decision, _graphic
from tests.fixtures.graphics import _style
from tests.fixtures.operations import assert_refused, execute_operations

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("kind", ["styles", "automatic-styles"])
def test_nested_foreign_style_payload_never_suppresses_real_graphic_alternatives(
    tmp_path: Path, kind: str
) -> None:
    document, frame = _graphic(tmp_path)
    body = document.tree(Part.CONTENT).find("office:body/office:text", NS)
    assert body is not None
    foreign = etree.SubElement(body, "{urn:example:opaque}payload")
    container = etree.SubElement(foreign, qn("office", kind))
    default = etree.SubElement(
        container, qn("style", "default-style"), {qn("style", "family"): "graphic"}
    )
    etree.SubElement(default, qn("style", "graphic-properties"), {qn("draw", "decorative"): "true"})
    role = effective_graphic_role(document, frame)
    assert not role.decorative
    assert role.problem is None
    source = document.save(tmp_path / "foreign-style.odt")
    assert "GRAPHIC003" in {finding.rule_id for finding in audit_odf(source).findings}


@pytest.mark.parametrize(
    ("part", "kind"), [(Part.STYLES, "styles"), (Part.CONTENT, "automatic-styles")]
)
def test_duplicate_applicable_style_containers_refuse_role_edits(
    tmp_path: Path, part: Part, kind: str
) -> None:
    document, frame = _graphic(tmp_path)
    etree.SubElement(document.tree(part).getroot(), qn("office", kind))
    role = effective_graphic_role(document, frame)
    assert role.problem
    operation = _decision(document, frame, decorative=True)
    before = document.checkpoint()
    assert operation.apply(document)[0].status == Status.FAILED
    assert not document.changed_since(before)


def test_common_generated_name_is_not_proven_output_and_cannot_shadow_a_peer(
    tmp_path: Path,
) -> None:

    document, frame = _graphic(tmp_path)
    _style(document, "Visual")
    frame.set(qn("draw", "style-name"), "Visual")
    parent = frame.getparent()
    assert parent is not None
    document.tree(Part.CONTENT)
    peer = deepcopy(frame)
    peer.set(qn("draw", "name"), "Peer")
    parent.append(peer)
    _ns, candidate = GraphicRoleEditor(document).derived(frame, decorative=True)
    name = candidate.get(qn("style", "name"), "")
    props = candidate.find("style:graphic-properties", NS)
    assert props is not None
    props.set(qn("draw", "decorative"), "false")
    common = document.tree(Part.STYLES).find("office:styles", NS)
    assert common is not None
    common.append(candidate)
    peer.set(qn("draw", "style-name"), name)
    assert normalized_role_attributes(document, peer) == {qn("draw", "style-name"): name}
    assert not effective_graphic_role(document, peer).decorative
    source = document.save(tmp_path / "collision.odt")
    original = source.read_bytes()
    destination = tmp_path / "destination.odt"
    destination.write_bytes(b"Existing destination")
    operation = _decision(document, frame, decorative=True)
    assert_refused(
        execute_operations(source, destination, [operation]),
        match="collides with an authored common style",
    )
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"Existing destination"
    reopened = OdfDocument.open(source)
    saved_peer = reopened.tree(Part.CONTENT).find(".//draw:frame[@draw:name='Peer']", NS)
    assert saved_peer is not None
    assert not effective_graphic_role(reopened, saved_peer).decorative


@pytest.mark.parametrize("default", [False, True])
def test_duplicate_graphic_properties_are_unresolved_and_cannot_hide_alternatives(
    tmp_path: Path, *, default: bool
) -> None:

    document, frame = _graphic(tmp_path)
    if default:
        common = document.tree(Part.STYLES).find("office:styles", NS)
        assert common is not None
        style = etree.SubElement(
            common, qn("style", "default-style"), {qn("style", "family"): "graphic"}
        )
        etree.SubElement(
            style, qn("style", "graphic-properties"), {qn("draw", "decorative"): "true"}
        )
    else:
        style = _style(document, "Role", role="true")
        document.tree(Part.CONTENT)
        frame.set(qn("draw", "style-name"), "Role")
    etree.SubElement(style, qn("style", "graphic-properties"), {qn("draw", "decorative"): "false"})
    assert effective_graphic_role(document, frame).problem
    operation = _decision(document, frame, decorative=False)
    before = document.checkpoint()
    assert operation.apply(document)[0].status == Status.FAILED
    assert not document.changed_since(before)
    source = document.save(tmp_path / "ambiguous-properties.odt")
    assert {"GRAPHIC001", "GRAPHIC003"} <= {
        finding.rule_id for finding in audit_odf(source).findings
    }


def test_odf13_decorative_declaration_is_unresolved_and_retains_missing_alternative(
    tmp_path: Path,
) -> None:

    document, frame = _graphic(tmp_path, "1.3")
    _style(document, "Role", role="true")
    document.tree(Part.CONTENT)
    frame.set(qn("draw", "style-name"), "Role")
    assert effective_graphic_role(document, frame).problem
    source = document.save(tmp_path / "unsupported-role.odt")
    assert {"GRAPHIC001", "GRAPHIC003"} <= {
        finding.rule_id for finding in audit_odf(source).findings
    }


@pytest.mark.parametrize("style_name", [None, "", "Authored"])
@pytest.mark.parametrize("namespace", ["draw", "presentation"])
def test_graphic_cascade_contains_only_present_names(
    style_name: str | None, namespace: str
) -> None:
    shape = etree.Element(qn("draw", "frame"))
    if style_name is not None:
        shape.set(qn(namespace, "style-name"), style_name)
    shape.set(qn(namespace, "class-names"), "First Second")
    family = "graphic" if namespace == "draw" else "presentation"
    expected = ([style_name] if style_name else []) + ["First", "Second"]
    assert GraphicStyles.context(shape) == (namespace, family, expected)
