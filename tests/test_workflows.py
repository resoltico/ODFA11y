# SPDX-License-Identifier: MPL-2.0
"""Supply-chain hygiene shared by every workflow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from odfa11y.pdf.export import MINIMUM_LIBREOFFICE_VERSION

WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github/workflows").glob("*.yml"))


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
    version = re.search(r'ODFA11Y_LIBREOFFICE_VERSION: "([0-9.]+)"', workflow.read_text())
    assert version is not None
    assert tuple(int(part) for part in version[1].split(".")) >= MINIMUM_LIBREOFFICE_VERSION
    readme = (workflow.parents[2] / "README.md").read_text()
    minimum = ".".join(str(part) for part in MINIMUM_LIBREOFFICE_VERSION)
    assert f"LibreOffice {minimum} or newer" in readme
