# SPDX-License-Identifier: MPL-2.0
"""Image descriptions preserve actual graphic resources and reject uninspectable inputs."""

from dataclasses import dataclass
from typing import ClassVar, override
lazy from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.concepts import GraphicIdentity
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import PlanError
from odfa11y.families import require_spec
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import load_plan
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.answers import (
    Authored,
    FaultEdit,
    apply_in_memory,
    graphic_answer,
    graphic_inputs,
    metadata_input,
)
from tests.fixtures.documents import make_flat
from tests.fixtures.operations import apply_answers, assert_refused
from tests.fixtures.paths import TESTS
from tests.fixtures.plans import plan_header, reviewed_plan

SOURCE = TESTS / "family_corpus/fruit-image.odi"


def _plan() -> list[Authored]:
    document = OdfDocument.open(SOURCE)
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    identity = GraphicIdentity(document, [frame])
    return [
        metadata_input(language="en-US"),
        graphic_inputs({
            "Fruit illustration": graphic_answer(
                "Fruit", "A red apple and a green pear", identity.fingerprint([frame])
            )
        }),
    ]


def _payload(document: OdfDocument) -> str:
    return select_elements(document.tree(Part.CONTENT), "//draw:image")[0].get(
        qn("xlink", "href"), ""
    )


@dataclass(frozen=True, slots=True)
class ChangeImageGeometry(FaultEdit):
    """Negative control changes image geometry rather than its alternative."""

    name: ClassVar[str] = "change_image_geometry"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
        frame.set(qn("svg", "width"), "1cm")
        return (Outcome(self.name, Status.APPLIED, "Changed geometry", count=1),)


def test_image_native_content_and_description_are_preserved_and_idempotent(tmp_path: Path) -> None:
    before = OdfDocument.open(SOURCE)
    assert validate(before).count == 0
    assert "GRAPHIC001" in {f.rule_id for f in audit_odf(SOURCE).findings}
    once, twice = tmp_path / "once.odi", tmp_path / "twice.odi"
    assert apply_answers(SOURCE, once, _plan()).changed
    assert not apply_answers(once, twice, _plan()).changed
    after = OdfDocument.open(twice)
    assert require_spec(before.kind).snapshot(before) == require_spec(after.kind).snapshot(after)
    assert before.storage.read(_payload(before)) == after.storage.read(_payload(after))
    assert once.read_bytes() == twice.read_bytes()
    assert validate(after).count == 0
    assert {f.rule_id for f in audit_odf(twice, schema=True).findings} == {"ODF009"}


def test_image_geometry_change_is_rejected_before_publication(tmp_path: Path) -> None:
    destination = tmp_path / "wrong.odi"
    assert_refused(
        apply_answers(SOURCE, destination, [ChangeImageGeometry()]), match="content changed"
    )
    assert not destination.exists()


def test_changed_actual_image_bytes_make_reviewed_description_stale() -> None:
    document = OdfDocument.open(SOURCE)
    plan = _plan()[-1]
    document.storage.write_member(
        _payload(document), b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'
    )
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(document, plan)
    assert not document.dirty


@pytest.mark.parametrize("profile", ["source", "verify"])
def test_image_source_profiles_do_not_claim_pdf_assurance(tmp_path: Path, profile: str) -> None:
    record = execute(
        SOURCE,
        reviewed_plan(SOURCE, _plan(), Pagination.SAME()),
        tmp_path / profile,
        RunSettings(profile=profile_named(profile)),
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    assert not (tmp_path / profile / "remediated.pdf").exists()
    if profile == "verify":
        assert any(stage.status == "not-applicable" for stage in record.stages)


@pytest.mark.parametrize(
    "payload",
    [
        b"not an image",
        b"<html/>",
        b'<!DOCTYPE svg [<!ENTITY secret SYSTEM "file:///private/secret">]><svg xmlns="http://www.w3.org/2000/svg"><text>&secret;</text></svg>',
    ],
)
def test_image_payload_integrity_rejects_malformed_or_unresolved_graphics(
    tmp_path: Path, payload: bytes
) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(_payload(document), payload)
    source = document.save(tmp_path / "broken.odi")
    report = audit_odf(source)
    assert "IMAGE002" in {f.rule_id for f in report.findings}
    assert "/private/secret" not in str(report.as_dict())


def test_image_external_reference_is_not_fetched_or_echoed(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    image = select_elements(document.tree(Part.CONTENT), "//draw:image")[0]
    resource = "https://person:secret@invalid.example/image.svg"
    image.set(qn("xlink", "href"), resource)
    source = document.save(tmp_path / "external.odi")
    report = audit_odf(source)
    assert "IMAGE005" in {f.rule_id for f in report.findings}
    assert resource not in str(report.as_dict())


def test_image_configuration_is_family_bound_and_strict(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text(
        plan_header(SOURCE)
        + (
            '[decisions."graphic.alternative"."content/frame[name=Fruit%20illustration]"]\n'
            'description = "Fruit"\n'
            'fingerprint = "0123456789abcdef"\n'
        )
    )
    [operation] = load_plan(plan).decisions
    assert operation.kind.id == "graphic.alternative"
    assert operation.answer.description == "Fruit"
    plan.write_text(
        plan_header(SOURCE)
        + '[decisions."graphic.alternative"."content/frame[1]"]\nalt_text = "Fruit"\n'
    )
    with pytest.raises(PlanError):
        load_plan(plan)


@pytest.mark.parametrize(
    "declaration",
    [
        '<script>throw "do not execute"</script>',
        '<image href="https://person:private@invalid.example/image.png"/>',
        "<rect onclick=\"fetch('https://invalid.example/')\"/>",
        '<rect fill="url(https://invalid.example/paint.svg)"/>',
        '<style>@import "https://invalid.example/style.css";</style>',
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">content</div></foreignObject>',
    ],
)
def test_svg_declared_dependencies_and_active_content_require_review(
    tmp_path: Path, declaration: str
) -> None:
    document = OdfDocument.open(SOURCE)
    payload = f'<svg xmlns="http://www.w3.org/2000/svg">{declaration}</svg>'.encode()
    document.storage.write_member(_payload(document), payload)
    report = audit_odf(document.save(tmp_path / "review.odi"))
    assert "IMAGE001" in {f.rule_id for f in report.findings}
    assert "invalid.example" not in str(report.as_dict())


def test_svg_external_stylesheet_requires_review(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(
        _payload(document),
        b'<?xml-stylesheet href="https://invalid.example/style.css"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg"/>',
    )
    report = audit_odf(document.save(tmp_path / "stylesheet.odi"))
    assert "IMAGE001" in {f.rule_id for f in report.findings}


def test_svg_self_contained_references_are_not_external_dependencies(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(
        _payload(document),
        b'<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="shape" d="M0,0 L1,1"/>'
        b'</defs><use href="#shape" fill="url(#paint)" style="stroke:url(\'#stroke\')"/></svg>',
    )
    report = audit_odf(document.save(tmp_path / "self-contained.odi"))
    assert not {"IMAGE002", "IMAGE001"} & {f.rule_id for f in report.findings}


def test_flat_image_embedded_payload_is_preserved_without_a_package_reference(
    tmp_path: Path,
) -> None:
    source = make_flat(tmp_path, "image")
    destination = tmp_path / "described.fodi"
    before = OdfDocument.open(source)
    binary = select_elements(before.tree(Part.CONTENT), "//office:binary-data")[0].text
    assert validate(before).count == 0
    apply_answers(
        source,
        destination,
        [graphic_inputs({"Picture": graphic_answer(description="One black pixel")})],
    )
    after = OdfDocument.open(destination)
    assert select_elements(after.tree(Part.CONTENT), "//office:binary-data")[0].text == binary
    assert not {"GRAPHIC001", "IMAGE005", "IMAGE002"} & {
        f.rule_id for f in audit_odf(destination).findings
    }


def test_flat_image_malformed_embedded_base64_has_an_integrity_finding(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "image")
    document = OdfDocument.open(source)
    select_elements(document.tree(Part.CONTENT), "//office:binary-data")[0].text = "%%%invalid%%%"
    report = audit_odf(document.save(tmp_path / "invalid.fodi"))
    assert "IMAGE002" in {f.rule_id for f in report.findings}


def test_svg_external_dtd_is_uninspectable_even_without_an_entity_reference(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(
        _payload(document),
        b'<!DOCTYPE svg SYSTEM "https://invalid.example/graphic.dtd">'
        b'<svg xmlns="http://www.w3.org/2000/svg"/>',
    )
    report = audit_odf(document.save(tmp_path / "external-dtd.odi"))
    assert "IMAGE002" in {f.rule_id for f in report.findings}
