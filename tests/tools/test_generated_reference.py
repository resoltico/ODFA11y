# SPDX-License-Identifier: MPL-2.0
"""Generated command/schema/capability references fail closed when stale."""

from __future__ import annotations

import shutil
import sys
from typing import TYPE_CHECKING

import pytest

from tests.fixtures.paths import REPOSITORY
from tools import generate_reference

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("name", ["CLI.md", "SCHEMAS.md", "CAPABILITIES.md"])
def test_stale_interface_reference_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    docs = tmp_path / "docs"
    (docs / "measurements").mkdir(parents=True)
    for source in ("PLAN.md", "RULES.md", "measurements/doctor.json"):
        shutil.copyfile(REPOSITORY / "docs" / source, docs / source)
    schemas = tmp_path / "src/odfa11y/schemas"
    schemas.mkdir(parents=True)
    monkeypatch.setattr(generate_reference, "SCHEMA_DIRECTORY", schemas)
    monkeypatch.setattr(sys, "argv", ["generate_reference"])
    assert generate_reference.main() == 0
    monkeypatch.setattr(sys, "argv", ["generate_reference", "--check"])
    assert generate_reference.main() == 0
    (docs / name).write_text("Stale interface description.\n")
    with pytest.raises(SystemExit) as error:
        generate_reference.main()
    assert error.value.code == 1
