# SPDX-License-Identifier: AGPL-3.0-only
"""Document workflows never conduct synthetic exporter capability experiments."""

from dataclasses import replace
from pathlib import Path

import pytest

from odfa11y.application import batch, run
from odfa11y.application.native import NativeTools
from odfa11y.families import probes
from tests.batch.test_batch import write_batch_file
from tests.fixtures.native import recording
from tests.fixtures.plans import plan_header, reviewed_plan
from tests.fixtures.writer import make_minimal_odt


def test_document_run_has_no_experiments_or_capability_record(
    tmp_path: Path, native_tools: NativeTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("A document run conducted a synthetic capability experiment")

    monkeypatch.setattr(probes, "measure_probe", forbidden)
    source = make_minimal_odt(tmp_path / "source.odt")
    exports = []
    native = replace(native_tools, export=recording(exports))
    result = run(source, reviewed_plan(source), tmp_path / "evidence", native_tools=native)
    assert result.exit_status == 0
    assert len(exports) == 2
    chain = result.as_dict()["toolchain"]
    assert isinstance(chain, dict)
    assert "capabilities" not in chain


def test_batch_items_do_not_share_or_conduct_experiments(
    tmp_path: Path, native_tools: NativeTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("A batch item conducted a synthetic capability experiment")

    monkeypatch.setattr(probes, "measure_probe", forbidden)
    source = make_minimal_odt(tmp_path / "source.odt")
    (tmp_path / "plan.toml").write_text(plan_header(source))
    batch_file = write_batch_file(
        tmp_path, [("first", "source.odt", "plan.toml"), ("second", "source.odt", "plan.toml")]
    )
    exports = []
    native = replace(native_tools, export=recording(exports))
    result = batch(batch_file, tmp_path / "evidence", native_tools=native)
    assert result.exit_status == 0
    assert len(exports) == 4
