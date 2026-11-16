# SPDX-License-Identifier: AGPL-3.0-only
"""Supply-chain hygiene shared by every workflow."""

import re
import tomllib
lazy from pathlib import Path

import pytest

from odfa11y.native.libreoffice import MINIMUM_LIBREOFFICE_VERSION
from tests.fixtures.paths import REPOSITORY

WORKFLOWS = sorted((REPOSITORY / ".github/workflows").glob("*.yml"))


def test_workflows_are_discovered() -> None:
    assert {path.name for path in WORKFLOWS} >= {"checks.yml", "audit.yml"}


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_every_action_is_pinned_to_a_commit(workflow: Path) -> None:
    references = re.findall(
        r"^\s+(?:- )?uses: (\S+)", workflow.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert references
    assert [ref for ref in references if not re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", ref)] == []


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_default_token_permissions_are_read_only(workflow: Path) -> None:
    assert re.search(
        r"^permissions:\n  contents: read\n", workflow.read_text(encoding="utf-8"), re.MULTILINE
    )


def test_the_pinned_linux_runtime_meets_the_supported_minimum() -> None:
    workflow = next(path for path in WORKFLOWS if path.name == "checks.yml")
    pins = tomllib.loads((REPOSITORY / "tools/native_versions.toml").read_text())
    version = pins["libreoffice"]["version"]
    assert tuple(int(part) for part in version.split(".")) >= MINIMUM_LIBREOFFICE_VERSION
    readme = (workflow.parents[2] / "README.md").read_text()
    minimum = ".".join(str(part) for part in MINIMUM_LIBREOFFICE_VERSION)
    assert f"LibreOffice {minimum} or newer" in readme
