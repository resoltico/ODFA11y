# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for required validator status."""

lazy from collections.abc import Callable
lazy from pathlib import Path

from odfa11y.application.tools import Tools
from odfa11y.evidence import check_bundle
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt


def test_real_production_reaches_missing_required_validator(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    target = tmp_path / "evidence"
    record = execute(
        source,
        reviewed_plan(source, [], FidelityPolicy()),
        target,
        RunSettings(
            tools=Tools(
                soffice=external_tool("soffice", "libreoffice"),
                verapdf=str(tmp_path / "missing-verapdf"),
            ),
            profile=profile_named("production"),
        ),
    )
    assert all(stage.status == "passed" for stage in record.stages[:7]), record.as_dict()
    assert record.failed_stage == "validate-pdf"
    assert record.exit_status == 3
    assert check_bundle(target) == []
