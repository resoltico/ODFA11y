# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for core examples."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from tests.fixtures.native_resources import writer_resource
from tools import core_examples


def test_native_examples_surface_real_fidelity_pipeline_and_integrity_results(
    tmp_path: Path, external_tool: Callable[..., str], capsys: pytest.CaptureFixture[str]
) -> None:
    source = writer_resource(tmp_path)
    before = source.read_bytes()
    comparison, record, problems = core_examples.native_work(
        source,
        tmp_path / "work",
        Tools(soffice=external_tool("soffice", "libreoffice")),
    )
    assert comparison.passed, comparison.as_dict()
    assert record.passed, record.as_dict()
    assert record.exit_status == 0
    assert problems == []
    assert (tmp_path / "work" / "publication.pdf").is_file()
    assert source.read_bytes() == before
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
