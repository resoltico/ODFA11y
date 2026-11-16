# SPDX-License-Identifier: MPL-2.0
"""Replacing the displayed source cannot change captured run input."""

import importlib
from contextlib import contextmanager
lazy from pathlib import Path

import pytest

from odfa11y.capture import source_digest
from odfa11y.odf import PackageStorage
from odfa11y.plans.fidelity import Pagination
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize("boundary", ["capture_source", "audit_odf", "execute_decisions"])
def test_source_replacement_uses_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    runner = importlib.import_module("odfa11y.run.engine")
    source = make_minimal_odt(tmp_path / "original.odt")
    original = source.read_bytes()
    digest = source_digest(source)
    method = getattr(runner, boundary)

    if boundary == "capture_source":

        @contextmanager
        def exchange(*args, **kwargs):
            with method(*args, **kwargs) as captured:
                source.write_bytes(b"replaced source")
                yield captured

    else:

        def exchange(*args, **kwargs):
            source.write_bytes(b"replaced source")
            return method(*args, **kwargs)

    monkeypatch.setattr(runner, boundary, exchange)
    target = tmp_path / "bundle"
    result = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        target,
        RunSettings(profile=profile_named("source")),
    )
    assert result.passed
    assert result.document.sha256 == digest
    assert (target / "remediated.odt").read_bytes() == original
    assert b"Body paragraph" in PackageStorage(target / "remediated.odt").read("content.xml")
    remediation = next(stage.remediation for stage in result.stages if stage.remediation)
    assert remediation.candidate is not None
    assert remediation.candidate.subject == "remediated.odt"
    assert not list(tmp_path.glob(".odfa11y-source-*"))
