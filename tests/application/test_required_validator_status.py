# SPDX-License-Identifier: MPL-2.0
"""Required validators are resolved during preparation, before stages or evidence."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from odfa11y import Profile, Tools, run
from odfa11y.cli import main
from odfa11y.errors import ToolUnavailable
from odfa11y.native.verapdf import find_verapdf
from tests.batch.test_batch import manifest_file
from tests.fixtures.native import native_fakes, recording
from tests.fixtures.pdf import tagged_writer
from tests.fixtures.plans import plan_header, reviewed_plan
from tests.fixtures.writer import make_minimal_odt


def test_required_validator_absence_runs_no_stage_and_leaves_no_bundle(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    exports = []
    events = []
    native = replace(native_fakes(), validator=find_verapdf, export=recording(exports))
    with pytest.raises(ToolUnavailable) as failure:
        run(
            source,
            reviewed_plan(source),
            tmp_path / "evidence",
            profile=Profile.PRODUCTION,
            tools=Tools(verapdf=tmp_path / "missing-validator"),
            native_tools=native,
            observer=events.append,
        )
    assert failure.value.exit_status == 3
    assert not exports
    assert [(event.step, event.state) for event in events] == [
        ("prepare", "running"),
        ("prepare", "failed"),
    ]
    assert not (tmp_path / "evidence").exists()


def test_cli_and_batch_keep_preparation_failure_status(tmp_path: Path, capsys) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = tmp_path / "plan.toml"
    plan.write_text(plan_header(source))
    native = replace(native_fakes(), validator=find_verapdf)
    missing = str(tmp_path / "missing-validator")
    assert (
        main(
            [
                "pipeline",
                str(source),
                "--plan",
                str(plan),
                "--output-dir",
                str(tmp_path / "single"),
                "--profile",
                "production",
                "--verapdf",
                missing,
            ],
            native_tools=native,
        )
        == 3
    )
    assert not (tmp_path / "single").exists()
    manifest = manifest_file(
        tmp_path, [("first", "source.odt", "plan.toml"), ("second", "source.odt", "plan.toml")]
    )
    assert (
        main(
            [
                "batch",
                str(manifest),
                "--output-dir",
                str(tmp_path / "batch"),
                "--profile",
                "production",
                "--verapdf",
                missing,
            ],
            native_tools=native,
        )
        == 3
    )
    record = json.loads((tmp_path / "batch" / "batch.json").read_text())
    assert [item["exit_status"] for item in record["items"]] == [3, 3]
    assert all(item["error"]["code"] == "tool-unavailable" for item in record["items"])
    assert all(item["evidence"] is None for item in record["items"])
    assert not (tmp_path / "batch" / "first").exists()
    assert "Traceback" not in capsys.readouterr().err


def test_validator_selection_does_not_request_validation(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "source.pdf"
    tagged_writer(["H1"]).write(pdf)
    args = ["audit", str(pdf), "--verapdf", str(tmp_path / "missing-validator")]
    assert main(args) == 0
    assert main([*args, "--validate"]) == 3
    output = capsys.readouterr()
    assert "VERA000" not in output.out
