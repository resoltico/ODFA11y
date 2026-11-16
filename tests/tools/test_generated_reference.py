# SPDX-License-Identifier: AGPL-3.0-only
"""Generated command/schema/capability references fail closed when stale."""

import shutil
import sys
lazy from pathlib import Path

import pytest

from tests.fixtures.paths import REPOSITORY
from tools import generate_reference


@pytest.mark.parametrize("name", ["CLI.md", "SCHEMAS.md", "CAPABILITIES.md"])
def test_stale_interface_reference_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    for source in ("PLAN.md", "RULES.md"):
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
