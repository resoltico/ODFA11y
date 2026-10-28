# SPDX-License-Identifier: MPL-2.0
"""Fail-closed inspection of exact GitHub release state and preserved asset bytes."""

from __future__ import annotations

import argparse
import json
import subprocess  # noqa: S404  Invoke selected local tools with argument lists.
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast


def _api(repository: str, endpoint: str, *, paginate: bool = False) -> object:
    args = ["gh", "api", f"repos/{repository}/{endpoint}"]
    if paginate:
        args.extend(["--paginate", "--slurp"])
    response = subprocess.run(args, check=True, capture_output=True, timeout=120)  # noqa: S603  Arguments select a local tool without a shell.
    return json.loads(response.stdout)


def _records(repository: str, endpoint: str) -> list[dict[str, object]]:
    pages = _api(repository, endpoint, paginate=True)
    if (
        not isinstance(pages, list)
        or not pages
        or any(not isinstance(page, list) for page in pages)
    ):
        msg = "GitHub query did not return a complete paginated list"
        raise ValueError(msg)
    records = [entry for page in pages for entry in page]
    if any(not isinstance(entry, dict) for entry in records):
        msg = "GitHub query returned malformed records"
        raise ValueError(msg)
    return cast("list[dict[str, object]]", records)


def release_for_tag(repository: str, tag: str) -> dict[str, object] | None:
    """Require a successful release inventory, including authenticated draft records.

    Returns
    -------
    dict[str, object] | None
        The sole matching release, or verified absence.

    Raises
    ------
    ValueError
        Records are malformed or multiple releases use the same tag.

    """
    releases = _records(repository, "releases?per_page=100")
    if any(
        not isinstance(r.get("tag_name"), str) or not isinstance(r.get("draft"), bool)
        for r in releases
    ):
        msg = "GitHub returned malformed release identity"
        raise ValueError(msg)
    found = [r for r in releases if r["tag_name"] == tag]
    if len(found) > 1:
        msg = "Multiple releases use the requested tag"
        raise ValueError(msg)
    return found[0] if found else None


def _tag_reference(repository: str, tag: str) -> dict[str, object] | None:
    refs = _records(repository, f"git/matching-refs/tags/{tag}")
    if any(
        not isinstance(r.get("ref"), str) or not isinstance(r.get("object"), dict) for r in refs
    ):
        msg = "GitHub returned malformed tag identity"
        raise ValueError(msg)
    exact = [r for r in refs if r["ref"] == "refs/tags/" + tag]
    if len(exact) > 1:
        msg = "Multiple exact tag references returned"
        raise ValueError(msg)
    return exact[0] if exact else None


def require_absent(repository: str, tag: str) -> None:
    """Abort on existing tags/releases or unsuccessful state queries.

    Raises
    ------
    ValueError
        A tag or draft/published release already exists.

    """
    reference = _tag_reference(repository, tag)
    release = release_for_tag(repository, tag)
    if reference is not None or release is not None:
        msg = f"Tag or release {tag} already exists; correction requires explicit draft handling"
        raise ValueError(msg)


@dataclass(frozen=True)
class ReleaseExpectation:
    """Preserved release inputs that state queries and downloads must match."""

    target: str
    assets: dict[str, bytes]
    notes: str


def verify_release(repository: str, tag: str, expected: ReleaseExpectation, *, draft: bool) -> None:
    """Inspect exact release state, notes, asset inventory and downloaded bytes.

    Raises
    ------
    ValueError
        State, target, notes, asset bytes or publication tag differs from tested inputs.

    """
    release = release_for_tag(repository, tag)
    if release is None or release["draft"] != draft:
        msg = "Release is absent or has the wrong publication state"
        raise ValueError(msg)
    if release.get("target_commitish") != expected.target or release.get("body") != expected.notes:
        msg = "Release target or exact changelog notes differs from tested inputs"
        raise ValueError(msg)
    assets = release.get("assets")
    if not isinstance(assets, list) or any(not isinstance(a, dict) for a in assets):
        msg = "Release asset inventory is malformed"
        raise ValueError(msg)
    if any(not isinstance(a.get("name"), str) for a in assets):
        msg = "Release asset name is malformed"
        raise ValueError(msg)
    names = [a.get("name") for a in assets]
    if len(names) != len(set(names)) or set(names) != expected.assets.keys():
        msg = "Release asset names differ from preserved tested artifacts"
        raise ValueError(msg)
    for asset in assets:
        identity = asset.get("id")
        if type(identity) is not int or asset.get("size") != len(expected.assets[asset["name"]]):
            msg = "Release asset identity or size is malformed"
            raise ValueError(msg)
        response = subprocess.run(  # noqa: S603  Arguments select a local tool without a shell.
            [  # noqa: S607  System tool is resolved through PATH.
                "gh",
                "api",
                f"repos/{repository}/releases/assets/{identity}",
                "-H",
                "Accept: application/octet-stream",
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        if response.stdout != expected.assets[asset["name"]]:
            msg = "Downloaded release asset differs from preserved tested bytes"
            raise ValueError(msg)
    _verify_tag(repository, tag, expected.target, draft=draft)


def _verify_tag(repository: str, tag: str, target: str, *, draft: bool) -> None:
    reference = _tag_reference(repository, tag)
    if draft:
        if reference is not None:
            msg = "Draft tag already exists; uniqueness/publication identity is unestablished"
            raise ValueError(msg)
        return
    if reference is None:
        msg = "Published release has no tag"
        raise ValueError(msg)
    obj = cast("dict[str, object]", reference["object"])
    for _ in range(8):
        if obj.get("type") == "commit" and obj.get("sha") == target:
            return
        if obj.get("type") != "tag" or not isinstance(obj.get("sha"), str):
            break
        record = _api(repository, "git/tags/" + cast("str", obj["sha"]))
        if not isinstance(record, dict) or not isinstance(record.get("object"), dict):
            break
        obj = cast("dict[str, object]", record["object"])
    msg = "Published tag does not peel to the tested commit"
    raise ValueError(msg)


def _inspect_arguments(args: argparse.Namespace) -> None:
    if args.mode == "absent":
        require_absent(args.repository, args.tag)
    else:
        wheels = list(args.directory.glob("*.whl"))
        archives = list(args.directory.glob("*.tar.gz"))
        if len(wheels) != 1 or len(archives) != 1:
            msg = "Release inspection requires exactly one wheel and one source archive"
            raise ValueError(msg)
        assets = {p.name: p.read_bytes() for p in (*wheels, *archives)}
        assets[args.checksums.name] = args.checksums.read_bytes()
        expectation = ReleaseExpectation(args.target, assets, args.notes.read_text())
        verify_release(args.repository, args.tag, expectation, draft=args.mode == "draft")


def main() -> int:
    """Run read-only pre-creation, pre-publication or post-publication verification.

    Returns
    -------
    int
        Zero only when all requested state and byte inspections succeeded.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("absent", "draft", "published"))
    parser.add_argument("repository")
    parser.add_argument("tag")
    parser.add_argument("--target")
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--checksums", type=Path)
    parser.add_argument("--notes", type=Path)
    args = parser.parse_args()
    if args.mode != "absent" and any(
        v is None for v in (args.target, args.directory, args.checksums, args.notes)
    ):
        parser.error("draft/published inspection requires target, directory, checksums and notes")
    try:
        _inspect_arguments(args)
    except OSError, ValueError, subprocess.SubprocessError:
        sys.stderr.write(
            "Release state inspection failed; absence or artifact identity was not established.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
