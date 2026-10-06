# SPDX-License-Identifier: MPL-2.0
"""Negative controls for tag and release-artifact identity."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from odfa11y import __version__
from tools.check_release import check_release


def _distributions(
    directory: Path, *, version: str = __version__, license_name: str = "MPL-2.0"
) -> None:
    metadata = (
        f"Name: odfa11y\nVersion: {version}\nRequires-Python: >=3.14\n"
        f"License-Expression: {license_name}\n"
    )
    root = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(directory / "odfa11y.whl", "w") as wheel:
        wheel.writestr("odfa11y.dist-info/METADATA", metadata)
        wheel.writestr("odfa11y.dist-info/licenses/LICENSE", (root / "LICENSE").read_bytes())
    with tarfile.open(directory / "odfa11y.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("odfa11y/PKG-INFO")
        encoded = metadata.encode()
        info.size = len(encoded)
        archive.addfile(info, io.BytesIO(encoded))


def test_matching_release_metadata_is_accepted(tmp_path: Path) -> None:
    _distributions(tmp_path)
    assert check_release(f"v{__version__}", tmp_path) == []


def test_tag_must_match_source_version(tmp_path: Path) -> None:
    assert any("must match" in error for error in check_release("v9.9.9", tmp_path))


@pytest.mark.parametrize(("version", "license_name"), [("9.9.9", "MPL-2.0"), (__version__, "MIT")])
def test_inconsistent_distribution_metadata_is_rejected(
    tmp_path: Path, version: str, license_name: str
) -> None:
    _distributions(tmp_path, version=version, license_name=license_name)
    assert check_release(f"v{__version__}", tmp_path)


def test_missing_artifacts_are_rejected(tmp_path: Path) -> None:
    assert any("exactly one" in error for error in check_release(f"v{__version__}", tmp_path))
