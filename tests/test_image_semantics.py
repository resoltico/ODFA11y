# SPDX-License-Identifier: MPL-2.0
"""Image descriptions preserve actual graphic resources and reject uninspectable inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

import pytest

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.config import load_config
from odfa11y.content import GraphicDescription, GraphicIdentity
from odfa11y.errors import ConfigError, RemediationError
from odfa11y.families import adapter_for
from odfa11y.families.image import SetGraphicDescriptions
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

from .documents import make_flat

SOURCE = Path(__file__).parent / "family_corpus/fruit-image.odi"


def _plan() -> list[Operation]:
    document = OdfDocument.open(SOURCE)
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    identity = GraphicIdentity(document, [frame])
    return [
        SetMetadata(language="en-US"),
        SetGraphicDescriptions({
            "Fruit illustration": GraphicDescription(
                "Fruit", "A red apple and a green pear", identity.fingerprint([frame])
            )
        }),
    ]


def _payload(document: OdfDocument) -> str:
    return select_elements(document.tree(Part.CONTENT), "//draw:image")[0].get(
        qn("xlink", "href"), ""
    )


@dataclass(frozen=True, slots=True)
class ChangeImageGeometry(Operation):
    """Negative control changes image geometry rather than its alternative."""

    name: ClassVar[str] = "change_image_geometry"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        frame = select_elements(document.edit(Part.CONTENT), "//draw:frame")[0]
        frame.set(qn("svg", "width"), "1cm")
        return (Outcome(self.name, Status.APPLIED, "Changed geometry", count=1),)


def test_image_native_content_and_description_are_preserved_and_idempotent(tmp_path: Path) -> None:
    before = OdfDocument.open(SOURCE)
    assert validate(before).count == 0
    assert "IMAGE002" in {f.rule_id for f in audit_odf(SOURCE).findings}
    once, twice = tmp_path / "once.odi", tmp_path / "twice.odi"
    assert remediate(SOURCE, once, _plan()).changed
    assert not remediate(once, twice, _plan()).changed
    after = OdfDocument.open(twice)
    assert adapter_for(before.kind).snapshot(before) == adapter_for(after.kind).snapshot(after)
    assert before.storage.read(_payload(before)) == after.storage.read(_payload(after))
    assert once.read_bytes() == twice.read_bytes()
    assert validate(after).count == 0
    assert {f.rule_id for f in audit_odf(twice, schema=True).findings} == {"ODF008"}


def test_image_geometry_change_is_rejected_before_publication(tmp_path: Path) -> None:
    destination = tmp_path / "wrong.odi"
    with pytest.raises(RemediationError, match="content changed"):
        remediate(SOURCE, destination, [ChangeImageGeometry()])
    assert not destination.exists()


def test_changed_actual_image_bytes_make_reviewed_description_stale() -> None:
    document = OdfDocument.open(SOURCE)
    plan = _plan()[-1]
    document.storage.write_member(
        _payload(document), b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'
    )
    assert plan.apply(document)[0].status is Status.FAILED
    assert document.edit_count == 0


@pytest.mark.parametrize("profile", ["inspect", "verify"])
def test_image_source_profiles_do_not_claim_pdf_assurance(tmp_path: Path, profile: str) -> None:
    record = run_pipeline(
        SOURCE, _plan(), FidelityPolicy(), tmp_path / profile, PipelineOptions(profile=profile)
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
    assert "IMAGE004" in {f.rule_id for f in report.findings}
    assert "/private/secret" not in str(report.as_dict())


def test_image_external_reference_is_not_fetched_or_echoed(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    image = select_elements(document.edit(Part.CONTENT), "//draw:image")[0]
    resource = "https://person:secret@invalid.example/image.svg"
    image.set(qn("xlink", "href"), resource)
    source = document.save(tmp_path / "external.odi")
    report = audit_odf(source)
    assert "IMAGE003" in {f.rule_id for f in report.findings}
    assert resource not in str(report.as_dict())


def test_image_configuration_is_family_bound_and_strict(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text('[image.graphics."Fruit illustration"]\ndescription = "Fruit"\n')
    assert isinstance(load_config(plan).operations[0], SetGraphicDescriptions)
    plan.write_text('[image]\nalt_text = "Fruit"\n')
    with pytest.raises(ConfigError):
        load_config(plan)


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
    assert "IMAGE005" in {f.rule_id for f in report.findings}
    assert "invalid.example" not in str(report.as_dict())


def test_svg_external_stylesheet_requires_review(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(
        _payload(document),
        b'<?xml-stylesheet href="https://invalid.example/style.css"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg"/>',
    )
    report = audit_odf(document.save(tmp_path / "stylesheet.odi"))
    assert "IMAGE005" in {f.rule_id for f in report.findings}


def test_svg_self_contained_references_are_not_external_dependencies(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(
        _payload(document),
        b'<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="shape" d="M0,0 L1,1"/>'
        b'</defs><use href="#shape"/></svg>',
    )
    report = audit_odf(document.save(tmp_path / "self-contained.odi"))
    assert not {"IMAGE004", "IMAGE005"} & {f.rule_id for f in report.findings}


def test_flat_image_embedded_payload_is_preserved_without_a_package_reference(
    tmp_path: Path,
) -> None:
    source = make_flat(tmp_path, "image")
    destination = tmp_path / "described.fodi"
    before = OdfDocument.open(source)
    binary = select_elements(before.tree(Part.CONTENT), "//office:binary-data")[0].text
    assert validate(before).count == 0
    remediate(
        source,
        destination,
        [SetGraphicDescriptions({"Picture": GraphicDescription(description="One black pixel")})],
    )
    after = OdfDocument.open(destination)
    assert select_elements(after.tree(Part.CONTENT), "//office:binary-data")[0].text == binary
    assert not {"IMAGE002", "IMAGE003", "IMAGE004"} & {
        f.rule_id for f in audit_odf(destination).findings
    }


def test_flat_image_malformed_embedded_base64_has_an_integrity_finding(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "image")
    document = OdfDocument.open(source)
    select_elements(document.edit(Part.CONTENT), "//office:binary-data")[0].text = "%%%invalid%%%"
    report = audit_odf(document.save(tmp_path / "invalid.fodi"))
    assert "IMAGE004" in {f.rule_id for f in report.findings}


def test_svg_external_dtd_is_uninspectable_even_without_an_entity_reference(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    document.storage.write_member(
        _payload(document),
        b'<!DOCTYPE svg SYSTEM "https://invalid.example/graphic.dtd">'
        b'<svg xmlns="http://www.w3.org/2000/svg"/>',
    )
    report = audit_odf(document.save(tmp_path / "external-dtd.odi"))
    assert "IMAGE004" in {f.rule_id for f in report.findings}
