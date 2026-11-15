# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for pipeline."""

import json
lazy from collections.abc import Callable
lazy from pathlib import Path

from odfa11y.application.tools import Tools
from odfa11y.concepts import GraphicAlternative
from odfa11y.evidence import check_bundle
from odfa11y.families.text import (
    MarkTableHeaders,
    RemoveEmptySpacers,
    SetGraphicAlternatives,
    TableHeaders,
)
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.progress import PIPELINE_STAGES
from odfa11y.remediate import SetMetadata
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt
from tests.run.test_pipeline import _document_with_spacers, statuses


def test_end_to_end_run_with_libreoffice_and_verapdf_produces_verified_evidence(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = make_minimal_odt(
        tmp_path / "doc.odt",
        features={"with_data_table": True, "with_image_without_alt": True},
    )
    operations = [
        SetMetadata(title="Evidence run", language="en-GB"),
        MarkTableHeaders({"Data": TableHeaders(1)}),
        SetGraphicAlternatives({"Logo": GraphicAlternative("Logo", "A sample logo")}),
    ]
    options = RunSettings(
        tools=Tools(soffice=soffice, verapdf=verapdf), profile=profile_named("production")
    )
    record = execute(
        source, reviewed_plan(source, operations, FidelityPolicy()), tmp_path / "out", options
    )
    why = [
        (
            stage.name,
            stage.reason,
            [f.message for f in stage.report.findings] if stage.report else [],
        )
        for stage in record.stages
        if stage.status != "passed"
    ]
    assert statuses(record) == dict.fromkeys(PIPELINE_STAGES, "passed"), why
    assert record.exit_status == 0
    assert check_bundle(tmp_path / "out") == []
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert run["toolchain"]["libreoffice"]["version"] != "unknown"
    assert run["toolchain"]["verapdf"]["name"] == "veraPDF"
    assert run["format"] == 3
    assert run["profile"]["name"] == "production"
    assert run["document"]["kind"] == "text"
    assert run["document"]["layout"] == "package"
    assert run["document"]["adapter"] == "text"
    assert len(run["plan_sha256"]) == 64
    assert {font["name"] for font in run["fonts"]["remediated"]}
    assert set(run["outputs"]) >= {"remediated.odt", "remediated.pdf", "source.pdf", "verapdf.xml"}
    assert "- [ ]" in (tmp_path / "out" / "REVIEW.md").read_text()


def test_layout_shifting_operations_fail_the_default_fidelity_gate_and_leave_diff_images(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = _document_with_spacers(tmp_path)
    options = RunSettings(tools=Tools(soffice=soffice))
    failed = execute(
        source,
        reviewed_plan(source, [RemoveEmptySpacers()], FidelityPolicy()),
        tmp_path / "strict",
        options,
    )
    assert statuses(failed)["fidelity"] == "failed"
    assert failed.exit_status == 2
    assert (tmp_path / "strict" / "fidelity" / "page-001-diff.png").is_file()
    allowed = FidelityPolicy(pagination="may-change")
    passed = execute(
        source,
        reviewed_plan(source, [RemoveEmptySpacers()], allowed),
        tmp_path / "relaxed",
        options,
    )
    assert statuses(passed)["fidelity"] == "passed"


def test_repeated_runs_have_equal_logical_results_and_identical_documents(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = make_minimal_odt(tmp_path / "doc.odt")
    options = RunSettings(tools=Tools(soffice=soffice))
    runs = [
        execute(
            source,
            reviewed_plan(source, [SetMetadata(title="Same")], FidelityPolicy()),
            tmp_path / f"r{i}",
            options,
        )
        for i in range(2)
    ]
    first, second = (json.loads((tmp_path / f"r{i}" / "run.json").read_text()) for i in range(2))
    assert first["stages"] == second["stages"]
    assert first["operations"] == second["operations"]
    assert first["outputs"]["remediated.odt"] == second["outputs"]["remediated.odt"]
    assert runs[0].passed
