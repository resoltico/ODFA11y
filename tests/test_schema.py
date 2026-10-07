# SPDX-License-Identifier: MPL-2.0
"""Bundled schemas: integrity, validation of synthetic documents and the differential rule."""

from __future__ import annotations

import itertools
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import odfa11y.odf.schema as module
from odfa11y.odf import (
    SUPPORTED_VERSIONS,
    OdtDocument,
    OdtPackage,
    SchemaResult,
    provenance,
    regressions,
    validate,
)

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from .fixtures import Features

FEATURES = [
    "with_plain_email",
    "with_data_table",
    "with_table_header",
    "with_image_without_alt",
    "add_blank_body_paragraph",
]


def test_bundled_schemas_match_their_recorded_digests_and_cover_every_version() -> None:
    recorded = provenance()
    for version in SUPPORTED_VERSIONS:
        assert f"OpenDocument-v{version}-schema.rng" in recorded
        assert f"OpenDocument-v{version}-manifest-schema.rng" in recorded
    assert all(
        entry["url"].startswith("https://docs.oasis-open.org/") for entry in recorded.values()
    )


def test_a_tampered_schema_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "schemas"
    directory.mkdir()
    original = Path(module.SCHEMA_DIRECTORY)
    for item in original.iterdir():
        (directory / item.name).write_bytes(item.read_bytes())
    target = directory / "OpenDocument-v1.4-schema.rng"
    target.write_bytes(target.read_bytes() + b"<!-- tampered -->")
    monkeypatch.setattr(module, "SCHEMA_DIRECTORY", directory)
    with pytest.raises(ValueError, match="does not match its recorded SHA-256"):
        provenance()


def test_provenance_file_is_valid_toml_with_one_entry_per_schema() -> None:
    text = (Path(__file__).parents[1] / "src/odfa11y/odf/schemas/PROVENANCE.toml").read_text()
    assert len(tomllib.loads(text)) == 2 * len(SUPPORTED_VERSIONS)


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
def test_every_synthetic_feature_combination_is_schema_valid(tmp_path: Path, version: str) -> None:
    for combination in itertools.product([False, True], repeat=len(FEATURES)):
        features = cast("Features", dict(zip(FEATURES, combination, strict=True)))
        if features["with_table_header"] and not features["with_data_table"]:
            continue
        document = OdtDocument.open(
            make_minimal_odt(tmp_path / "x.odt", version=version, **features)
        )
        assert validate(document).violations == {}, features


def test_markup_that_libreoffice_tolerates_is_rejected(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "x.odt", with_data_table=True)
    package = OdtPackage(source)
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"<table:table-column/>", b"")
    )
    package.save(tmp_path / "bad.odt")
    result = validate(OdtDocument.open(tmp_path / "bad.odt"))
    assert result.available
    assert "content.xml" in result.violations
    assert result.count > 0


def test_unsupported_versions_report_no_schema(tmp_path: Path) -> None:
    result = validate(OdtDocument.open(make_minimal_odt(tmp_path / "x.odt", version="1.2")))
    assert (result.available, result.version) == (False, "1.2")


def test_regressions_compare_message_multisets_per_member() -> None:
    before = SchemaResult("1.4", available=True, violations={"styles.xml": ("a", "a", "b")})
    same = SchemaResult("1.4", available=True, violations={"styles.xml": ("b", "a")})
    worse = SchemaResult(
        "1.4", available=True, violations={"styles.xml": ("a", "a", "a"), "content.xml": ("c",)}
    )
    assert regressions(before, same) == {}
    assert regressions(before, worse) == {"styles.xml": ("a",), "content.xml": ("c",)}
