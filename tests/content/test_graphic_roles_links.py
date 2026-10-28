# SPDX-License-Identifier: MPL-2.0
"""Reviewed graphic roles and normative link descriptions protect their source boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.content import GraphicAlternative, LinkDescription, graphics_fingerprint
from odfa11y.content.graphic_styles import (
    GraphicStyles,
    effective_graphic_role,
    normalized_role_attributes,
)
from odfa11y.content.links import link_fingerprint, link_has_description, link_location
from odfa11y.families.text import SetGraphicAlternatives, SetLinkDescriptions
from odfa11y.odf import NS, OdfDocument, Part, qn, select_elements, validate
from odfa11y.source_audit import audit_odf
from tests.fixtures.graphics import _style
from tests.fixtures.writer import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def _graphic(tmp_path: Path, version: str = "1.4") -> tuple[OdfDocument, etree._Element]:
    document = OdfDocument.open(
        make_minimal_odt(
            tmp_path / "graphic.odt", version=version, features={"with_image_without_alt": True}
        )
    )
    return document, select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]


def _decision(
    document: OdfDocument, frame: etree._Element, *, decorative: bool
) -> SetGraphicAlternatives:
    return SetGraphicAlternatives({
        frame.get(qn("draw", "name"), ""): GraphicAlternative(
            decorative=decorative, fingerprint=graphics_fingerprint(document, [frame])
        )
    })


@pytest.mark.parametrize("automatic", [False, True])
def test_isolated_role_preserves_shared_style_and_reapplies(
    tmp_path: Path, *, automatic: bool
) -> None:
    document, frame = _graphic(tmp_path)
    _style(document, "Shared", automatic=automatic)
    frame.set(qn("draw", "style-name"), "Shared")
    peer = deepcopy(frame)
    peer.set(qn("draw", "name"), "Peer")
    parent = frame.getparent()
    assert parent is not None
    parent.append(peer)
    before = graphics_fingerprint(document, [frame])
    operation = _decision(document, frame, decorative=True)
    assert operation.apply(document)[0].status == Status.APPLIED
    assert effective_graphic_role(document, frame).decorative
    assert not effective_graphic_role(document, peer).decorative
    assert normalized_role_attributes(document, frame) == {qn("draw", "style-name"): "Shared"}
    assert graphics_fingerprint(document, [frame]) == before
    assert operation.apply(document)[0].status == Status.UNCHANGED
    assert len(
        select_elements(document.tree(Part.CONTENT), "//style:style[@style:family='graphic']")
    ) == 1 + int(automatic)
    assert validate(document).count == 0
    assert _decision(document, frame, decorative=False).apply(document)[0].status == Status.APPLIED
    assert not effective_graphic_role(document, frame).decorative
    assert not effective_graphic_role(document, peer).decorative
    assert validate(document).count == 0


def test_ordered_class_overlay_and_common_parent_remain_legal(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    _style(document, "Parent", role="true")
    _style(document, "Automatic", automatic=True, parent="Parent")
    _style(document, "Overlay", role="false")
    frame.set(qn("draw", "style-name"), "Automatic")
    frame.set(qn("draw", "class-names"), "Overlay")
    assert not effective_graphic_role(document, frame).decorative
    operation = _decision(document, frame, decorative=True)
    assert operation.apply(document)[0].status == Status.APPLIED
    assert frame.get(qn("draw", "class-names"), "").startswith("Overlay ODFA11yRole_")
    assert effective_graphic_role(document, frame).decorative
    assert operation.apply(document)[0].status == Status.UNCHANGED
    assert validate(document).count == 0


@pytest.mark.parametrize("problem", ["missing", "duplicate", "cycle", "mixed", "invalid"])
def test_unresolved_roles_refuse_without_mutation(tmp_path: Path, problem: str) -> None:
    document, frame = _graphic(tmp_path)
    frame.set(qn("draw", "style-name"), "Role")
    if problem != "missing":
        _style(
            document,
            "Role",
            role="perhaps" if problem == "invalid" else None,
            parent="Role" if problem == "cycle" else None,
        )
    if problem == "duplicate":
        _style(document, "Role")
    if problem == "mixed":
        style = _style(document, "Presentation")
        style.set(qn("style", "family"), "presentation")
        frame.set(qn("presentation", "style-name"), "Presentation")
    operation = _decision(document, frame, decorative=True)
    checkpoint = document.checkpoint()
    assert operation.apply(document)[0].status == Status.FAILED
    assert not document.changed_since(checkpoint)
    assert effective_graphic_role(document, frame).problem


@pytest.mark.parametrize("kind", ["text", "control", "ancestor-link", "event"])
def test_decorative_intent_refuses_text_or_interactive_context(tmp_path: Path, kind: str) -> None:
    document, frame = _graphic(tmp_path)
    _style(document, "Visual")
    frame.set(qn("draw", "style-name"), "Visual")
    if kind == "text":
        etree.SubElement(frame, qn("text", "p")).text = "Caption"
    elif kind == "control":
        etree.SubElement(frame, qn("draw", "control"))
    elif kind == "event":
        etree.SubElement(frame, qn("office", "event-listeners"))
    else:
        parent = frame.getparent()
        assert parent is not None
        parent.remove(frame)
        etree.SubElement(parent, qn("draw", "a")).append(frame)
    assert _decision(document, frame, decorative=True).apply(document)[0].status == Status.FAILED


@pytest.mark.parametrize("role", [False, True])
def test_any_explicit_role_requires_odf14(tmp_path: Path, *, role: bool) -> None:
    document, frame = _graphic(tmp_path, "1.3")
    assert _decision(document, frame, decorative=role).apply(document)[0].status == Status.FAILED


def test_authored_style_drift_invalidates_review_and_payload_remains_checked(
    tmp_path: Path,
) -> None:
    document, frame = _graphic(tmp_path)
    style = _style(document, "Authored")
    frame.set(qn("draw", "style-name"), "Authored")
    operation = _decision(document, frame, decorative=True)
    props = style.find("style:graphic-properties", NS)
    assert props is not None
    props.set(qn("draw", "fill-color"), "#ffffff")
    assert operation.apply(document)[0].status == Status.FAILED
    assert _decision(document, frame, decorative=True).apply(document)[0].status == Status.APPLIED
    image = frame.find("draw:image", NS)
    assert image is not None
    image.set(qn("xlink", "href"), "https://example.test/missing.svg")
    document.save(tmp_path / "external.odt")
    report = audit_odf(tmp_path / "external.odt")
    assert "GRAPHIC003" not in {f.rule_id for f in report.findings}
    assert "NATIVE001" in {f.rule_id for f in report.findings}


def test_blank_alternatives_and_overlapping_roles_preflight_together(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    reviewed = graphics_fingerprint(document, [frame])
    for entries in (
        {"Logo": GraphicAlternative(title=" ")},
        {
            "Logo": GraphicAlternative(decorative=True, fingerprint=reviewed),
            "logo.svg": GraphicAlternative(description="A company logo"),
        },
        {
            "Logo": GraphicAlternative(decorative=True, fingerprint=reviewed),
            "logo.svg": GraphicAlternative(decorative=False, fingerprint=reviewed),
        },
    ):
        assert all(
            outcome.status == Status.FAILED
            for outcome in SetGraphicAlternatives(entries).apply(document)
        )
        assert not document.dirty


def test_link_description_preserves_normative_targets_and_reapplies(tmp_path: Path) -> None:
    document, _frame = _graphic(tmp_path)
    para = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    link = etree.SubElement(
        para,
        qn("text", "a"),
        {
            qn("xlink", "href"): "https://example.test/",
            qn("office", "name"): "Existing target name",
        },
    )
    assert not link_has_description(link)
    fingerprint = link_fingerprint(document, link)
    operation = SetLinkDescriptions({
        link_location(link, 1).path: LinkDescription("Example documentation", fingerprint)
    })
    assert operation.apply(document)[0].status == Status.APPLIED
    assert link_has_description(link)
    assert link.get(qn("office", "name")) == "Existing target name"
    assert link.get(qn("xlink", "href")) == "https://example.test/"
    assert link_fingerprint(document, link) == fingerprint
    assert operation.apply(document)[0].status == Status.UNCHANGED
    link.set(qn("xlink", "href"), "https://changed.test/")
    assert operation.apply(document)[0].status == Status.FAILED


@pytest.mark.parametrize("declared", ["true", "false"])
def test_group_role_refuses_and_does_not_hide_child_findings(tmp_path: Path, declared: str) -> None:
    document, frame = _graphic(tmp_path)
    _style(document, "Group", role=declared)
    parent = frame.getparent()
    assert parent is not None
    document.tree(Part.CONTENT)
    parent.remove(frame)
    group = etree.SubElement(
        parent, qn("draw", "g"), {qn("draw", "name"): "Group", qn("draw", "style-name"): "Group"}
    )
    inner = etree.SubElement(group, qn("draw", "g"))
    inner.append(frame)
    assert _decision(document, group, decorative=True).apply(document)[0].status == Status.FAILED
    source = document.save(tmp_path / "group.odt")
    ids = {finding.rule_id for finding in audit_odf(source).findings}
    assert {"GRAPHIC001", "GRAPHIC003"} <= ids


def test_decorative_authored_alternatives_remain_and_warn(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    _style(document, "Visual")
    frame.set(qn("draw", "style-name"), "Visual")
    title = etree.SubElement(frame, qn("svg", "title"))
    title.text = "Authored title"
    assert _decision(document, frame, decorative=True).apply(document)[0].status == Status.APPLIED
    source = document.save(tmp_path / "conflict.odt")
    assert {"GRAPHIC002"} <= {finding.rule_id for finding in audit_odf(source).findings}
    assert title.text == "Authored title"


def test_unproven_generated_style_cannot_normalize_geometry_or_visual_drift(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    _style(document, "Visual")
    frame.set(qn("draw", "style-name"), "Visual")
    operation = _decision(document, frame, decorative=True)
    assert operation.apply(document)[0].status == Status.APPLIED
    name = frame.get(qn("draw", "style-name"), "")
    generated = GraphicStyles(document).style("graphic", name)
    props = generated.find("style:graphic-properties", NS)
    assert props is not None
    props.set(qn("draw", "fill-color"), "#123456")
    assert normalized_role_attributes(document, frame) == {qn("draw", "style-name"): name}
    assert operation.apply(document)[0].status == Status.FAILED


def test_equal_style_names_in_distinct_legal_scopes_are_not_a_cycle(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    common = _style(document, "Shared", role="true")
    _style(document, "Shared", automatic=True, parent="Shared")
    frame.set(qn("draw", "style-name"), "Shared")
    role = effective_graphic_role(document, frame)
    assert role.problem is None
    assert role.decorative
    reviewed = _decision(document, frame, decorative=False)
    props = common.find("style:graphic-properties", NS)
    assert props is not None
    props.set(qn("draw", "fill-color"), "#ffffff")
    assert reviewed.apply(document)[0].status == Status.FAILED
    assert _decision(document, frame, decorative=False).apply(document)[0].status == Status.APPLIED
    assert not effective_graphic_role(document, frame).decorative
    assert validate(document).count == 0
