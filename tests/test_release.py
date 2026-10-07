# SPDX-License-Identifier: MPL-2.0
"""Negative controls for tag and release-artifact identity."""

from __future__ import annotations

import io
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from odfa11y import __version__
from tools.check_release import check_release

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "src/odfa11y/odf/schemas/NOTICE.txt"
LICENSE_EXPRESSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["license"]


@dataclass(frozen=True)
class Variant:
    """How a synthetic release differs from a correct one."""

    version: str = __version__
    license_name: str = LICENSE_EXPRESSION
    wheel_files: dict[str, bytes | None] = field(default_factory=dict)
    sdist_notice: bytes | None = (ROOT / NOTICE).read_bytes()


def _distributions(directory: Path, variant: Variant | None = None) -> None:
    variant = variant or Variant()
    metadata = (
        f"Name: odfa11y\nVersion: {variant.version}\nRequires-Python: >=3.14\n"
        f"License-Expression: {variant.license_name}\n"
    )
    files: dict[str, bytes | None] = {
        path.relative_to(ROOT / "src").as_posix(): path.read_bytes()
        for path in (ROOT / "src/odfa11y").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    files["odfa11y.dist-info/METADATA"] = metadata.encode()
    files["odfa11y.dist-info/licenses/LICENSE"] = (ROOT / "LICENSE").read_bytes()
    files[f"odfa11y.dist-info/licenses/{NOTICE}"] = (ROOT / NOTICE).read_bytes()
    files.update(variant.wheel_files)
    with zipfile.ZipFile(directory / "odfa11y.whl", "w") as wheel:
        for name, data in files.items():
            if data is not None:
                wheel.writestr(name, data)
    with tarfile.open(directory / "odfa11y.tar.gz", "w:gz") as archive:
        members = {"odfa11y/PKG-INFO": metadata.encode()}
        if variant.sdist_notice is not None:
            members[f"odfa11y/{NOTICE}"] = variant.sdist_notice
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_matching_release_metadata_is_accepted(tmp_path: Path) -> None:
    _distributions(tmp_path)
    assert check_release(f"v{__version__}", tmp_path) == []


def test_tag_must_match_source_version(tmp_path: Path) -> None:
    assert any("must match" in error for error in check_release("v9.9.9", tmp_path))


@pytest.mark.parametrize(
    ("version", "license_name"), [("9.9.9", LICENSE_EXPRESSION), (__version__, "MIT")]
)
def test_inconsistent_distribution_metadata_is_rejected(
    tmp_path: Path, version: str, license_name: str
) -> None:
    _distributions(tmp_path, Variant(version=version, license_name=license_name))
    assert check_release(f"v{__version__}", tmp_path)


def test_missing_artifacts_are_rejected(tmp_path: Path) -> None:
    assert any("exactly one" in error for error in check_release(f"v{__version__}", tmp_path))


def test_an_altered_schema_notice_in_the_wheel_is_rejected(tmp_path: Path) -> None:
    _distributions(
        tmp_path, Variant(wheel_files={f"odfa11y.dist-info/licenses/{NOTICE}": b"altered"})
    )
    errors = check_release(f"v{__version__}", tmp_path)
    assert any("NOTICE.txt does not match" in error for error in errors)


def test_a_source_archive_without_the_schema_notice_is_rejected(tmp_path: Path) -> None:
    _distributions(tmp_path, Variant(sdist_notice=None))
    errors = check_release(f"v{__version__}", tmp_path)
    assert any("missing the bundled-schema notice" in error for error in errors)


def test_an_altered_schema_notice_in_the_source_archive_is_rejected(tmp_path: Path) -> None:
    _distributions(tmp_path, Variant(sdist_notice=b"altered"))
    assert any("does not match" in error for error in check_release(f"v{__version__}", tmp_path))


def test_a_wheel_missing_a_package_file_is_rejected(tmp_path: Path) -> None:
    _distributions(tmp_path, Variant(wheel_files={"odfa11y/py.typed": None}))
    errors = check_release(f"v{__version__}", tmp_path)
    assert any("odfa11y/py.typed" in error for error in errors)


def test_a_wheel_with_an_unexpected_package_file_is_rejected(tmp_path: Path) -> None:
    _distributions(tmp_path, Variant(wheel_files={"odfa11y/stray_secrets.txt": b""}))
    errors = check_release(f"v{__version__}", tmp_path)
    assert any("stray_secrets.txt" in error for error in errors)
