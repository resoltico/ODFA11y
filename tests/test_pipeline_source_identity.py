# SPDX-License-Identifier: MPL-2.0
"""Replacing the displayed source cannot change captured run input."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from odfa11y.evidence import sha256_file
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import PackageStorage
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("boundary", ["sha256_file", "audit_odf", "remediate"])
def test_source_replacement_uses_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    runner = importlib.import_module("odfa11y.pipeline.run")
    source = make_minimal_odt(tmp_path / "original.odt")
    original = source.read_bytes()
    digest = sha256_file(source)
    method = getattr(runner, boundary)

    def replace(*args: object, **kwargs: object) -> object:
        source.write_bytes(b"replaced source")
        return method(*args, **kwargs)

    monkeypatch.setattr(runner, boundary, replace)
    target = tmp_path / "bundle"
    result = run_pipeline(source, [], FidelityPolicy(), target, PipelineOptions(profile="inspect"))
    assert result.passed
    assert result.document["sha256"] == digest
    assert (target / "remediated.odt").read_bytes() == original
    assert b"Body paragraph" in PackageStorage(target / "remediated.odt").read("content.xml")
    assert not list(tmp_path.glob(".odfa11y-source-*"))
