# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for cli."""

import json
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.cli import main
from tests.cli.test_cli import config
from tests.fixtures.writer import make_minimal_odt


def test_export_compare_and_run_with_real_libreoffice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = make_minimal_odt(tmp_path / "a.odt")
    pdf = tmp_path / "a.pdf"
    assert main(["export", str(source), str(pdf), "--soffice", soffice]) == 0
    assert pdf.is_file()
    capsys.readouterr()
    assert (
        main(["compare", str(source), str(source), "--soffice", soffice, "--format", "json"]) == 0
    )
    comparison = json.loads(capsys.readouterr().out)
    fidelity = next(
        row for row in comparison["report"]["facts"] if row["producer"] == "pdf-fidelity"
    )
    assert fidelity["raster_max_changed_ratio"] == 0.0
    assert main(["audit", str(pdf)]) == 0
    capsys.readouterr()
    arguments = ["run", str(source), "--plan", str(config(tmp_path)), "--soffice", soffice]
    assert main([*arguments, "--output-dir", str(tmp_path / "ev")]) == 0
    assert main(["verify-evidence", str(tmp_path / "ev")]) == 0
