# SPDX-License-Identifier: MPL-2.0
"""Require version tags and distribution metadata to agree before a draft release."""

from __future__ import annotations

import argparse
import email
import hashlib
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y import __version__

if TYPE_CHECKING:
    from email.message import Message


def check_release(tag: str, directory: Path) -> list[str]:
    """Verify the tag and the wheel/source archive selected for release.

    Returns
    -------
    list[str]
        Metadata or inventory failures; an empty list means consistency.

    """
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if tag != f"v{__version__}":
        return [f"Tag {tag!r} must match package version v{__version__}"]
    wheels = list(directory.glob("*.whl"))
    archives = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(archives) != 1:
        return ["Release requires exactly one wheel and one source archive"]
    errors: list[str] = []
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            return ["Wheel must contain exactly one package metadata record"]
        metadata = email.message_from_bytes(wheel.read(names[0]))
        errors.extend(_metadata_errors(metadata, project))
        errors.extend(_wheel_license_errors(wheel, root, project["license-files"]))
        errors.extend(_wheel_inventory_errors(wheel, root))
    with tarfile.open(archives[0]) as archive:
        names = [member for member in archive.getmembers() if member.name.endswith("/PKG-INFO")]
        if len(names) != 1:
            return [*errors, "Source archive must contain exactly one package metadata record"]
        stream = archive.extractfile(names[0])
        if stream is None:
            return [*errors, "Source archive metadata is not a regular file"]
        errors.extend(_metadata_errors(email.message_from_bytes(stream.read()), project))
        prefix = names[0].name.removesuffix("/PKG-INFO")
        errors.extend(_sdist_license_errors(archive, root, project["license-files"]))
        errors.extend(_sdist_inventory_errors(archive, root, prefix))
    return errors


def _wheel_license_errors(
    wheel: zipfile.ZipFile, root: Path, license_files: list[str]
) -> list[str]:
    errors = []
    for relative in license_files:
        found = [name for name in wheel.namelist() if name.endswith(f"/licenses/{relative}")]
        if len(found) != 1 or wheel.read(found[0]) != (root / relative).read_bytes():
            errors.append(f"Wheel {relative} does not match the repository file")
    return errors


def _sdist_license_errors(
    archive: tarfile.TarFile, root: Path, license_files: list[str]
) -> list[str]:
    errors = []
    for relative in license_files:
        found = [m for m in archive.getmembers() if m.name.endswith(f"/{relative}")]
        stream = archive.extractfile(found[0]) if len(found) == 1 and found[0].isfile() else None
        if stream is None or stream.read() != (root / relative).read_bytes():
            errors.append(f"Source archive {relative} does not match the repository file")
    return errors


def _wheel_inventory_errors(wheel: zipfile.ZipFile, root: Path) -> list[str]:
    shipped = {
        name: wheel.read(name)
        for name in wheel.namelist()
        if name.startswith("odfa11y/") and not name.endswith("/")
    }
    return _package_errors(shipped, root, "Wheel")


def _sdist_inventory_errors(archive: tarfile.TarFile, root: Path, prefix: str) -> list[str]:
    package_prefix = f"{prefix}/src/"
    shipped: dict[str, bytes] = {}
    for member in archive.getmembers():
        if member.isfile() and member.name.startswith(f"{package_prefix}odfa11y/"):
            stream = archive.extractfile(member)
            if stream is not None:
                shipped[member.name.removeprefix(package_prefix)] = stream.read()
    return _package_errors(shipped, root, "Source archive")


def _package_errors(shipped: dict[str, bytes], root: Path, kind: str) -> list[str]:
    """Compare package bytes with source and normative schema digests.

    Returns
    -------
    list[str]
        Missing, unexpected, altered or unverified package files.

    """
    package = root / "src"
    expected = {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in (package / "odfa11y").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    errors = [
        f"{kind} file set differs from src/odfa11y: {name}"
        for name in sorted(expected.keys() ^ shipped.keys())
    ]
    errors.extend(
        f"{kind} package file differs from source: {name}"
        for name in sorted(expected.keys() & shipped.keys())
        if expected[name] != shipped[name]
    )
    recorded = tomllib.loads((package / "odfa11y/odf/schemas/PROVENANCE.toml").read_text())
    for name, entry in recorded.items():
        relative = f"odfa11y/odf/schemas/{name}"
        if relative in shipped and hashlib.sha256(shipped[relative]).hexdigest() != entry["sha256"]:
            errors.append(f"{kind} schema does not match its normative digest: {name}")
    return errors


def extract_release_notes(changelog: str, version: str) -> str:
    """Extract the matching changelog section without rewriting its Markdown.

    Returns
    -------
    str
        The section including its heading, with only outer whitespace trimmed.

    Raises
    ------
    ValueError
        The requested version section is missing or appears more than once.

    """
    lines = changelog.splitlines(keepends=True)
    heading = f"## [{version}]"
    starts = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == heading or line.startswith(heading + " ")
    ]
    if not starts:
        msg = f"CHANGELOG.md has no section for {version}"
        raise ValueError(msg)
    if len(starts) != 1:
        msg = f"CHANGELOG.md has multiple sections for {version}"
        raise ValueError(msg)
    start = starts[0]
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return "".join(lines[start:end]).strip()


def _metadata_errors(metadata: Message, project: dict[str, object]) -> list[str]:
    expected = {
        "Name": project["name"],
        "Version": __version__,
        "Requires-Python": project["requires-python"],
        "License-Expression": project["license"],
    }
    return [
        f"Distribution {field} is {metadata[field]!r}; expected {value!r}"
        for field, value in expected.items()
        if metadata[field] != value
    ]


def _write_release_notes(output: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    changelog = (root / "CHANGELOG.md").read_bytes().decode("utf-8")
    notes = extract_release_notes(changelog, __version__)
    output.write_bytes((notes + "\n").encode("utf-8"))


def main() -> int:
    """Report inconsistent release inputs and return their status.

    Returns
    -------
    int
        Zero for consistent inputs; one for invalid artifacts or metadata.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--notes-output", type=Path, help="Write the exact matching changelog section."
    )
    args = parser.parse_args()
    try:
        errors = check_release(args.tag, args.directory)
        if not errors and args.notes_output is not None:
            _write_release_notes(args.notes_output)
    except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        errors = [f"Cannot inspect release artifacts: {exc}"]
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
