# SPDX-License-Identifier: MPL-2.0
"""Read Ruff JSON as bytes so Windows locale codecs cannot corrupt its Unicode text."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from tools import lint_policy
from tools.check_quality import check_repository

if TYPE_CHECKING:
    from pathlib import Path


def test_ruff_utf8_catalogue_is_decoded_as_json_without_locale_text_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.odfa11y.quality]\nmax-file-lines = 300\n"
        '[tool.ruff.lint]\nselect = ["ALL"]\n'
        "[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"
        '"example.py" = ["print"]\n'
    )
    source = tmp_path / "example.py"
    source.write_text("print('visible')\n")
    catalogue = json.dumps(
        [{"name": "print", "code": "T201", "explanation": "A “quotation” in Ruff documentation."}],
        ensure_ascii=False,
    ).encode("utf-8")
    assert b"\x9d" in catalogue
    with pytest.raises(UnicodeDecodeError):
        catalogue.decode("cp1252")
    findings = json.dumps([{"filename": str(source.resolve()), "code": "T201"}]).encode()
    outputs = iter([catalogue, findings])
    calls = []

    def transport(command: list[str], **options: object) -> SimpleNamespace:
        assert not options.get("text")
        assert "encoding" not in options
        assert options["capture_output"] is True
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=next(outputs))

    monkeypatch.setattr(lint_policy.subprocess, "run", transport)
    assert check_repository(tmp_path) == []
    assert len(calls) == 2
