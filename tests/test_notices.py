# SPDX-License-Identifier: MPL-2.0
"""Legal compliance: bundled OASIS files ship unmodified, with their notice and terms."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src/odfa11y/odf/schemas"
NOTICE = (SCHEMAS / "NOTICE.txt").read_text(encoding="utf-8")
PERMISSION = (
    "provided that the above copyright notice and this section are included on all such "
    "copies and derivative works. However, this document itself may not be modified in any way"
)
YEARS = {"1.3": "2021", "1.4": "2025"}


def test_the_notice_reproduces_the_oasis_terms_for_every_bundled_version() -> None:
    assert NOTICE.count(PERMISSION) == len(YEARS)
    assert NOTICE.count('"AS IS" basis and OASIS DISCLAIMS ALL WARRANTIES') == len(YEARS)
    for year in YEARS.values():
        assert f"Copyright © OASIS Open {year}. All Rights Reserved." in NOTICE


@pytest.mark.parametrize("version", sorted(YEARS))
def test_every_schema_file_keeps_its_oasis_copyright_header_unmodified(version: str) -> None:
    for kind in ("schema", "manifest-schema"):
        text = (SCHEMAS / f"OpenDocument-v{version}-{kind}.rng").read_text(encoding="utf-8")
        assert (
            f"Copyright (c) OASIS Open {YEARS[version]}. All Rights Reserved."
            in text.split("-->")[0]
        )
        assert f"https://docs.oasis-open.org/office/OpenDocument/v{version}/os/schemas/" in text


def test_the_notice_names_every_bundled_file_and_its_source() -> None:
    recorded = tomllib.loads((SCHEMAS / "PROVENANCE.toml").read_text(encoding="utf-8"))
    assert recorded
    for name, entry in recorded.items():
        assert name in NOTICE
        assert entry["url"].rsplit("/", 1)[0] in NOTICE


def test_the_package_declares_the_third_party_terms_in_its_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "MPL-2.0 AND LicenseRef-OASIS-ODF-Notice"
    assert "src/odfa11y/odf/schemas/NOTICE.txt" in project["license-files"]
    assert "LICENSE" in project["license-files"]


def test_git_never_rewrites_the_schema_files() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.rng -text" in attributes


def test_the_readme_points_readers_to_the_third_party_notice() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "src/odfa11y/odf/schemas/NOTICE.txt" in readme
