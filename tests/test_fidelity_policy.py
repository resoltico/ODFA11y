# SPDX-License-Identifier: MPL-2.0
"""Invalid fidelity choices refuse before export or evidence publication."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from odfa11y.cli import main
from odfa11y.config import load_config
from odfa11y.errors import ConfigError
from odfa11y.fidelity import FidelityPolicy

from .fixtures import make_minimal_odt
from .pdf_fixtures import text_pdf

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_policy_refuses_cli_before_publication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text(f"[fidelity]\nraster_tolerance = {value}\n")
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    output = tmp_path / "evidence"
    assert (
        main([
            "pipeline",
            str(source),
            "--config",
            str(plan),
            "--output-dir",
            str(output),
            "--profile",
            "inspect",
            "--format",
            "json",
        ])
        == 3
    )
    result = capsys.readouterr()
    assert not result.out
    assert "fidelity.raster_tolerance" in result.err
    assert "finite non-negative" in result.err
    assert not output.exists()
    assert source.read_bytes() == before
    with pytest.raises(ConfigError, match="raster_tolerance"):
        load_config(plan)
    with pytest.raises(ConfigError, match="raster_tolerance"):
        FidelityPolicy(raster_tolerance=float(value))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pagination", "typo"),
        ("pagination", []),
        ("raster_tolerance", True),
        ("raster_tolerance", "0.1"),
        ("raster_tolerance", -1),
        ("raster_tolerance", 10**400),
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
    with pytest.raises(ConfigError, match=field):
        FidelityPolicy(**cast("dict[str, Any]", {field: value}))


@pytest.mark.parametrize("pagination", ["same", "may-change"])
def test_finite_policy_boundaries_serialize_standard_json(pagination: str) -> None:
    for threshold in (0, 255):
        for tolerance in (0, 5.0, 1e308):
            policy = FidelityPolicy(pagination, tolerance, threshold, 1)
            assert json.loads(json.dumps(policy.as_dict(), allow_nan=False)) == policy.as_dict()


def test_toml_enormous_positive_dpi_has_controlled_cli_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = text_pdf(tmp_path / "dpi.pdf", [["Unchanged"]])
    plan = tmp_path / "dpi.toml"
    plan.write_text(f"[fidelity]\ndpi = {10**400}\n")
    assert load_config(plan).fidelity.dpi == 10**400
    assert main(["compare", str(pdf), str(pdf), "--config", str(plan)]) == 3
    output = capsys.readouterr()
    assert "DPI exceeds the numeric range" in output.err
    assert "Traceback" not in output.err
    assert not output.out
