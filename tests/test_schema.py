# SPDX-License-Identifier: MPL-2.0
"""Bundled schemas: integrity, validation of synthetic documents and the differential rule."""

from __future__ import annotations

import itertools
import shutil
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from lxml import etree

import odfa11y.odf.schema as module
from odfa11y.odf import (
    SUPPORTED_VERSIONS,
    OdfDocument,
    PackageStorage,
    Part,
    SchemaResult,
    Violation,
    provenance,
    qn,
    regressions,
    select_elements,
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
        entry["url"].startswith((
            "https://docs.oasis-open.org/",
            "https://www.w3.org/Math/RelaxNG/mathml3/",
        ))
        for entry in recorded.values()
    )


def test_a_tampered_schema_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "schemas"
    original = Path(module.SCHEMA_DIRECTORY)
    shutil.copytree(original, directory)
    target = directory / "OpenDocument-v1.4-schema.rng"
    target.write_bytes(target.read_bytes() + b"<!-- tampered -->")
    monkeypatch.setattr(module, "SCHEMA_DIRECTORY", directory)
    with pytest.raises(ValueError, match="does not match its recorded SHA-256"):
        provenance()


def test_provenance_file_is_valid_toml_with_one_entry_per_schema() -> None:
    text = (Path(__file__).parents[1] / "src/odfa11y/odf/schemas/PROVENANCE.toml").read_text()
    directory = Path(module.SCHEMA_DIRECTORY)
    assert set(tomllib.loads(text)) == {
        path.relative_to(directory).as_posix() for path in directory.rglob("*.rng")
    }


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
def test_every_synthetic_feature_combination_is_schema_valid(tmp_path: Path, version: str) -> None:
    for combination in itertools.product([False, True], repeat=len(FEATURES)):
        features = cast("Features", dict(zip(FEATURES, combination, strict=True)))
        if features["with_table_header"] and not features["with_data_table"]:
            continue
        document = OdfDocument.open(
            make_minimal_odt(tmp_path / "x.odt", version=version, **features)
        )
        assert validate(document).violations == {}, features


def test_markup_that_libreoffice_tolerates_is_rejected(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "x.odt", with_data_table=True)
    package = PackageStorage(source)
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"<table:table-column/>", b"")
    )
    package.save(tmp_path / "bad.odt")
    result = validate(OdfDocument.open(tmp_path / "bad.odt"))
    assert result.available
    assert "content.xml" in result.violations
    assert result.count > 0


def test_unsupported_versions_report_no_schema(tmp_path: Path) -> None:
    result = validate(OdfDocument.open(make_minimal_odt(tmp_path / "x.odt", version="1.2")))
    assert (result.available, result.version) == (False, "1.2")


def located(message: str, fingerprint: str) -> Violation:
    """Build a violation with a location fingerprint.

    Returns
    -------
    Violation
        The violation.

    """
    return Violation(message, fingerprint)


def test_regressions_compare_violations_per_member() -> None:
    first, second = located("a", "1"), located("b", "2")
    before = SchemaResult("1.4", available=True, violations={"styles.xml": (first, first, second)})
    same = SchemaResult("1.4", available=True, violations={"styles.xml": (second, first, first)})
    worse = SchemaResult(
        "1.4",
        available=True,
        violations={"styles.xml": (first, first, first), "content.xml": (located("c", "3"),)},
    )
    assert regressions(before, same) == {}
    assert regressions(before, worse) == {"styles.xml": ("a",), "content.xml": ("c",)}


def test_a_fixed_violation_cannot_hide_the_same_message_introduced_elsewhere() -> None:
    before = SchemaResult(
        "1.4", available=True, violations={"content.xml": (located("Did not expect x", "AAAA"),)}
    )
    after = SchemaResult(
        "1.4", available=True, violations={"content.xml": (located("Did not expect x", "BBBB"),)}
    )
    assert regressions(before, after) == {"content.xml": ("Did not expect x",)}


def test_violations_without_a_location_fall_back_to_counts() -> None:
    one = SchemaResult("1.4", available=True, violations={"content.xml": (Violation("m"),)})
    two = SchemaResult("1.4", available=True, violations={"content.xml": (Violation("m"),) * 2})
    assert regressions(one, one) == {}
    assert regressions(one, two) == {"content.xml": ("m",)}
    assert two.unlocated == 2


def _bogus(document: OdfDocument, *, at_start: bool) -> etree._Element:
    body = select_elements(document.edit(Part.CONTENT), "//office:text")[0]
    element = etree.Element(qn("text", "bogus"))
    body.insert(0, element) if at_start else body.append(element)
    return element


def test_the_real_validator_locates_a_violation_that_moved(tmp_path: Path) -> None:
    before = OdfDocument.open(make_minimal_odt(tmp_path / "before.odt"))
    _bogus(before, at_start=False)
    after = OdfDocument.open(make_minimal_odt(tmp_path / "after.odt"))
    _bogus(after, at_start=True)
    found = validate(before)
    assert found.unlocated == 0
    assert regressions(found, validate(after)) != {}


def test_an_unrelated_edit_does_not_turn_an_old_violation_into_a_new_one(tmp_path: Path) -> None:
    before = OdfDocument.open(make_minimal_odt(tmp_path / "before.odt"))
    _bogus(before, at_start=False)
    after = OdfDocument.open(make_minimal_odt(tmp_path / "after.odt"))
    _bogus(after, at_start=False)
    body = select_elements(after.edit(Part.CONTENT), "//office:text")[0]
    body.insert(0, etree.Element(qn("text", "p")))  # far from the violation
    assert regressions(validate(before), validate(after)) == {}
