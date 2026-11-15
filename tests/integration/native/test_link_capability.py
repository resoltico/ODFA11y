# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for link capability."""

import json
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from odfa11y.cli import main
from odfa11y.concepts import document_links, link_fingerprint
from odfa11y.evidence import check_bundle
from odfa11y.families.text.probes import LINK_PURPOSE, write_link_probe
from odfa11y.native.export import ExportSettings, export_pdfua, identify_soffice
from odfa11y.native.probes import ProbeId
from odfa11y.odf import OdfDocument, PackageStorage, validate
from odfa11y.pdf import audit_pdfua, validate_pdfua
from odfa11y.plans.fidelity import Pagination
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from tests.application.test_link_capability import LINK_BODY, WRITER
from tests.fixtures.answers import link_answer, link_inputs
from tests.fixtures.paths import TESTS
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt


def test_doctor_agrees_with_the_audit_of_a_real_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    package = PackageStorage(make_minimal_odt(tmp_path / "base.odt"))
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + LINK_BODY, 1),
    )
    linked = tmp_path / "linked.odt"
    package.save(linked)
    pdf = export_pdfua(linked, tmp_path / "linked.pdf", ExportSettings(WRITER, soffice=soffice))
    assert "PDF019" in {f.rule_id for f in audit_pdfua(pdf).findings}
    result = validate_pdfua(pdf, executable=external_tool("verapdf"))
    link_failures = {("7.18.1", "2"), ("7.18.5", "2")}
    assert {(f.clause, f.test_number) for f in result.failures} == link_failures

    assert main(["doctor", "--soffice", soffice, "--format", "json"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["toolchain"]["libreoffice"]["version"] == identify_soffice(soffice).version
    reported = next(
        item["status"]
        for item in doctor["toolchain"]["capabilities"]
        if item["id"] == "link-descriptions"
    )
    titled_probe = write_link_probe(tmp_path)
    probe_pdf = export_pdfua(
        titled_probe, tmp_path / "title-probe.pdf", ExportSettings(WRITER, soffice=soffice)
    )
    expected_support = (
        "unsupported"
        if "PDF019" in {f.rule_id for f in audit_pdfua(probe_pdf).findings}
        else "supported"
    )
    assert reported == expected_support

    document = OdfDocument.open(linked)
    record = execute(
        linked,
        reviewed_plan(
            linked,
            [
                link_inputs({
                    "content/link[1]": link_answer(
                        LINK_PURPOSE, link_fingerprint(document, document_links(document)[0])
                    )
                })
            ],
            Pagination.SAME(),
        ),
        tmp_path / "evidence",
        RunSettings(tools=Tools(soffice=soffice)),
    )
    assert (
        next(
            item.status.value
            for item in record.toolchain.capabilities
            if item.id == ProbeId.LINK_DESCRIPTIONS
        )
        == reported
    )
    assert record.toolchain.libreoffice is not None
    assert record.toolchain.libreoffice.version == doctor["toolchain"]["libreoffice"]["version"]
    evidence = json.loads((tmp_path / "evidence" / "run.json").read_text())
    assert (
        next(
            item["status"]
            for item in evidence["toolchain"]["capabilities"]
            if item["id"] == "link-descriptions"
        )
        == reported
    )
    assert not any("probe" in name for name in evidence["outputs"])
    assert check_bundle(tmp_path / "evidence") == []


@pytest.mark.parametrize("named", [False, True], ids=["unnamed", "explicit-name"])
def test_the_one_link_reproduction_and_explicit_name_control(
    tmp_path: Path, external_tool: Callable[..., str], *, named: bool
) -> None:
    source = TESTS / "reproductions" / "unnamed-link.odt"
    assert validate(OdfDocument.open(source)).count == 0
    package = PackageStorage(source)
    assert package.read("content.xml").count(b"<text:a ") == 1
    if named:
        package.write_member(
            "content.xml",
            package.read("content.xml").replace(
                b"<text:a ", b'<text:a office:name="Example site" '
            ),
        )
        source = package.save(tmp_path / "named-link.odt")
        assert validate(OdfDocument.open(source)).count == 0
    pdf = export_pdfua(
        source,
        tmp_path / "link.pdf",
        ExportSettings(WRITER, soffice=external_tool("soffice", "libreoffice")),
    )
    report = audit_pdfua(pdf)
    result = validate_pdfua(pdf, executable=external_tool("verapdf"))
    failures = {(f.clause, f.test_number) for f in result.failures}
    assert failures == (set() if named else {("7.18.1", "2"), ("7.18.5", "2")}), failures
    assert ("PDF019" in {f.rule_id for f in report.findings}) == (not named)
    if named:
        assert report.error_count == 0
        assert result.compliant
        record = execute(
            source,
            reviewed_plan(source, [], Pagination.SAME()),
            tmp_path / "named-evidence",
            RunSettings(tools=Tools(soffice=external_tool("soffice", "libreoffice"))),
        )
        assert record.passed, record.as_dict()
        assert check_bundle(tmp_path / "named-evidence") == []
