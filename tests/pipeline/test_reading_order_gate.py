# SPDX-License-Identifier: MPL-2.0
"""Production retains the floating-frame review gate while inline asset controls can pass."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y import Tools, profile_named, run
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.remediation import SetMetadata
from tests.fixtures.native_resources import writer_resource
from tests.fixtures.plans import reviewed_plan

if TYPE_CHECKING:
    from pathlib import Path


def test_production_requires_floating_frame_review_before_native_export(tmp_path: Path) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    frame.set(qn("text", "anchor-type"), "paragraph")
    document.save(source)
    record = run(
        source,
        reviewed_plan(source, [SetMetadata(language="en-GB")]),
        tmp_path / "evidence",
        profile=profile_named("production"),
        tools=Tools(soffice="not-a-real-tool"),
    )
    assert record.failed_stage == "audit-remediated"
    assert record.exit_status == 1
    stage = next(stage for stage in record.stages if stage.name == "audit-remediated")
    assert stage.report is not None
    assert "ORDER001" in {finding.rule_id for finding in stage.report.findings}
    assert not (tmp_path / "evidence/source.pdf").exists()
