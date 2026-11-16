# SPDX-License-Identifier: AGPL-3.0-only
"""Invalid fidelity choices refuse before export or evidence publication."""

import json
lazy from pathlib import Path

import pytest

from odfa11y.cli import main
from odfa11y.contracts import decode
from odfa11y.errors import PlanError
from odfa11y.plans.fidelity import FidelityPolicy, Pagination
from odfa11y.remediate.catalogue import load_plan
from tests.fixtures.pdf import text_pdf
from tests.fixtures.plans import plan_header
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_policy_refuses_cli_before_publication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text(
        plan_header(tmp_path / "source.odt") + f"[fidelity]\nraster_tolerance = {value}\n"
    )
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    output = tmp_path / "evidence"
    assert (
        main([
            "run",
            str(source),
            "--plan",
            str(plan),
            "--output-dir",
            str(output),
            "--profile",
            "source",
            "--format",
            "json",
        ])
        == 4
    )
    result = capsys.readouterr()
    assert not result.out
    assert "fidelity.raster_tolerance" in result.err
    assert "finite" in result.err
    assert not output.exists()
    assert source.read_bytes() == before
    with pytest.raises(PlanError, match="raster_tolerance"):
        load_plan(plan)
    with pytest.raises(PlanError, match="raster_tolerance"):
        Pagination.SAME(raster_tolerance=float(value))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pagination", "typo"),
        ("pagination", []),
        ("raster_tolerance", True),
        ("raster_tolerance", "0.1"),
        ("raster_tolerance", -1),
        ("ink_threshold", True),
        ("ink_threshold", 200.0),
        ("ink_threshold", -1),
        ("ink_threshold", 256),
        ("dpi", True),
        ("dpi", 72.0),
        ("dpi", 0),
    ],
)
def test_library_rejects_invalid_policy(field: str, value: object) -> None:
    with pytest.raises(PlanError, match=field):
        decode(FidelityPolicy, {field: value}, label="fidelity", error=PlanError)


@pytest.mark.parametrize(
    "policy",
    [
        Pagination.SAME(0, 0),
        Pagination.SAME(5.0, 255),
        Pagination.SAME(1e308),
        Pagination.MAY_CHANGE,
    ],
)
def test_finite_policy_boundaries_serialize_standard_json(policy: FidelityPolicy) -> None:
    assert json.loads(json.dumps(policy.as_dict(), allow_nan=False)) == policy.as_dict()


def test_retired_dpi_setting_is_refused_before_rendering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = text_pdf(tmp_path / "dpi.pdf", [["Unchanged"]])
    plan = tmp_path / "dpi.toml"
    plan.write_text(plan_header(tmp_path / "source.odt") + f"[fidelity]\ndpi = {10**400}\n")
    with pytest.raises(PlanError, match="dpi"):
        load_plan(plan)
    assert main(["compare", str(pdf), str(pdf), "--plan", str(plan)]) == 4
    output = capsys.readouterr()
    assert "dpi" in output.err
    assert "Traceback" not in output.err
    assert not output.out
