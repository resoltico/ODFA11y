# SPDX-License-Identifier: MPL-2.0
"""Independent archive inventory controls include contributor and corpus bytes."""

from __future__ import annotations

import io
import tarfile
from typing import TYPE_CHECKING

import pytest

from tools.source_inventory import archive_errors, source_files

if TYPE_CHECKING:
    from pathlib import Path

FILES = {
    "docs/guide.md": b"Contributor documentation",
    "tests/corpus/document.odt": b"\x00\xffinvented binary corpus",
    "tools/check.py": b"pass\n",
    "pyproject.toml": b"[project]\n",
    ".gitignore": b".venv/\n",
}


def inventory_fixture(
    root: Path, changes: dict[str, bytes | None]
) -> tuple[tarfile.TarFile, io.BytesIO]:
    for name, content in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    shipped: dict[str, bytes | None] = {**FILES, "PKG-INFO": b"Generated metadata", **changes}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in shipped.items():
            if data is not None:
                info = tarfile.TarInfo("release/" + name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    buffer.seek(0)
    return tarfile.open(fileobj=buffer), buffer


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("replacement", [None, b"altered"])
def test_every_contributor_material_is_required_byte_for_byte(
    tmp_path: Path, name: str, replacement: bytes | None
) -> None:
    archive, buffer = inventory_fixture(tmp_path, {name: replacement})
    with archive, buffer:
        assert any(name in e for e in archive_errors(archive, tmp_path, "release"))


@pytest.mark.parametrize("name", ["extra.txt", "../escape", "/absolute", "a/../escape", "a//alias"])
def test_unexpected_or_unsafe_authored_members_reject(tmp_path: Path, name: str) -> None:
    archive, buffer = inventory_fixture(tmp_path, {name: b"unexpected"})
    with archive, buffer:
        assert archive_errors(archive, tmp_path, "release")


def test_extracted_inventory_needs_no_git_and_allows_only_generated_packaging_metadata(
    tmp_path: Path,
) -> None:
    archive, buffer = inventory_fixture(tmp_path, {})
    with archive, buffer:
        assert archive_errors(archive, tmp_path, "release") == []
    assert source_files(tmp_path) == FILES


def test_duplicate_members_are_not_collapsed_by_dictionary_comparison(tmp_path: Path) -> None:
    archive, buffer = inventory_fixture(tmp_path, {})
    archive.close()
    buffer.seek(0)
    with tarfile.open(fileobj=buffer, mode="a") as append:
        info = tarfile.TarInfo("release/docs/guide.md")
        info.size = len(FILES["docs/guide.md"])
        append.addfile(info, io.BytesIO(FILES["docs/guide.md"]))
    buffer.seek(0)
    with tarfile.open(fileobj=buffer) as amended, buffer:
        assert any("duplicate" in e for e in archive_errors(amended, tmp_path, "release"))
