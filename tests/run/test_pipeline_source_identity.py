# SPDX-License-Identifier: MPL-2.0
"""Replacing the displayed source cannot change captured run input."""

import importlib
from contextlib import contextmanager
from dataclasses import replace
from typing import Any, cast
lazy from pathlib import Path

import pytest

from odfa11y.capture import source_digest
from odfa11y.errors import InvalidOption
from odfa11y.odf import Family, Layout, OdfDocument, PackageStorage
from odfa11y.plans.fidelity import Pagination
from odfa11y.status import Profile
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.records import record
from tests.fixtures.runs import RunSettings, execute
from tests.fixtures.schema import assert_record_schema
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize("boundary", ["capture_source", "audit_document", "execute_decisions"])
def test_source_replacement_uses_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    runner = importlib.import_module(
        "odfa11y.application.run" if boundary == "capture_source" else "odfa11y.run.stages"
    )
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
        RunSettings(profile=Profile.parse("source")),
    )
    assert result.passed
    assert result.source_sha256 == digest
    assert (target / "remediated.odt").read_bytes() == original
    assert b"Body paragraph" in PackageStorage(target / "remediated.odt").read("content.xml")
    remediation = next(stage.remediation for stage in result.stages if stage.remediation)
    assert remediation.candidate is not None
    assert remediation.candidate.subject == "remediated.odt"
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_run_carries_the_typed_detection_result_and_captured_identity(tmp_path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    result = execute(
        source, reviewed_plan(source), tmp_path / "bundle", RunSettings(profile=Profile.SOURCE)
    )
    assert result.document == OdfDocument.open(source).detection
    assert result.document.layout is Layout.PACKAGE
    assert result.document.kind is not None
    assert result.document.kind.family is Family.TEXT
    assert result.source_name == "doc.odt"
    assert result.source_sha256 == source_digest(source)
    value = assert_record_schema(result)
    document_value = value["document"]
    assert isinstance(document_value, dict)
    kind_value = document_value["kind"]
    assert isinstance(kind_value, dict)
    assert kind_value["family"] == "text"
    assert "family" not in document_value
    assert "sha256" not in document_value


@pytest.mark.parametrize("field", ["kind", "layout", "family"])
def test_run_serialization_refuses_bogus_detection_values(field: str) -> None:
    result = record()
    assert_record_schema(result)
    detection = result.document
    invalid = cast(Any, "bogus")
    if field == "family":
        assert detection.kind is not None
        detection = replace(detection, kind=replace(detection.kind, family=invalid))
    else:
        detection = replace(detection, **{field: invalid})
    with pytest.raises(InvalidOption):
        replace(result, document=detection).as_dict()
