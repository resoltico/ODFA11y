# SPDX-License-Identifier: AGPL-3.0-only
"""Production retains the floating-frame review gate while inline asset controls can pass."""

lazy from pathlib import Path

from odfa11y import Profile, run
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.rules import registry as rules
from tests.fixtures.answers import metadata_input
from tests.fixtures.native_resources import writer_resource
from tests.fixtures.plans import reviewed_plan


def test_production_retains_floating_frame_warning_and_continues_exports(
    tmp_path: Path, native_tools
) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    frame.set(qn("text", "anchor-type"), "paragraph")
    document.save(source)
    record = run(
        source,
        reviewed_plan(source, [metadata_input(language="en-GB")]),
        tmp_path / "evidence",
        profile=Profile.parse("production"),
        native_tools=native_tools,
    )
    assert record.failed_stage == "audit-remediated"
    assert record.exit_status == 1
    stage = next(stage for stage in record.stages if stage.name == "audit-remediated")
    assert stage.report is not None
    assert rules.ORDER002.id in {finding.rule_id for finding in stage.report.findings}
    assert (tmp_path / "evidence/source.pdf").exists()
    assert (tmp_path / "evidence/remediated.pdf").exists()
