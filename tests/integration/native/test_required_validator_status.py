# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for required validator status."""

lazy from collections.abc import Callable
lazy from pathlib import Path

from odfa11y.application.tools import Tools
from odfa11y.evidence import check_bundle
from odfa11y.plans.fidelity import Pagination
from odfa11y.status import Profile
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.runs import RunSettings, execute
from tests.fixtures.writer import make_minimal_odt


def test_real_production_reaches_missing_required_validator(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    target = tmp_path / "evidence"
    record = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        target,
        RunSettings(
            tools=Tools(
                soffice=external_tool("soffice", "libreoffice"),
                verapdf=str(tmp_path / "missing-verapdf"),
            ),
            profile=Profile.parse("production"),
        ),
    )
    assert all(stage.outcome.status == "passed" for stage in record.stages[:7]), record.as_dict()
    assert record.failed_stage == "validate-pdf"
    assert record.exit_status == 3
    assert check_bundle(target) == []
