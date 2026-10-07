# SPDX-License-Identifier: MPL-2.0
"""Check centralized lint exceptions against real analyzer results and negative controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from odfa11y.external_tools import run_bounded
from tools.check_quality import check_repository, check_types

BASE = """[tool.odfa11y.quality]
max-file-lines = 300
[tool.ruff]
preview = true
[tool.ruff.lint]
select = ["ALL"]
"""


def _repository(root: Path, settings: str, source: str = "print('visible')\n") -> None:
    (root / "pyproject.toml").write_text(BASE + settings, encoding="utf-8")
    (root / "example.py").write_text(source, encoding="utf-8")


@pytest.mark.parametrize("selector", ["print", "T201"])
def test_exact_current_rule_with_reason_and_real_diagnostic_is_accepted(
    tmp_path: Path, selector: str
) -> None:
    settings = (
        "\n[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"
        f'"example.py" = ["{selector}"]\n'
    )
    _repository(tmp_path, settings)
    assert check_repository(tmp_path) == []


@pytest.mark.parametrize("selector", ["ALL", "S", "not-a-ruff-rule"])
def test_blanket_prefix_or_unknown_selectors_are_rejected(tmp_path: Path, selector: str) -> None:
    settings = (
        "\n[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"
        f'"example.py" = ["{selector}"]\n'
    )
    _repository(tmp_path, settings)
    assert any("one exact Ruff rule" in error for error in check_repository(tmp_path))


@pytest.mark.parametrize("table", ["per-file-ignores", "extend-per-file-ignores"])
def test_existing_python_without_actual_diagnostic_has_unused_exception(
    tmp_path: Path, table: str
) -> None:
    _repository(
        tmp_path,
        f'\n[tool.ruff.lint.{table}]\n# CLI output is stdout.\n"example.py" = ["print"]\n',
        "value = 1\n",
    )
    assert any("unused lint exception: print" in error for error in check_repository(tmp_path))


def test_unmasking_additive_ignores_really_exposes_their_diagnostics(tmp_path: Path) -> None:
    _repository(
        tmp_path,
        "\n[tool.ruff.lint.extend-per-file-ignores]\n# Reviewed test invariant.\n"
        '"example.py" = ["assert"]\n',
        "assert False\n",
    )
    assert check_repository(tmp_path) == []


@pytest.mark.parametrize("pattern", ["notes.txt", "folder", ".venv/**", "dist/**"])
def test_exception_must_match_authored_python_not_data_directories_or_generated_files(
    tmp_path: Path, pattern: str
) -> None:
    (tmp_path / "notes.txt").write_text("print('data')")
    for directory in ("folder", ".venv", "dist"):
        (tmp_path / directory).mkdir()
    (tmp_path / ".venv/generated.py").write_text("print('generated')")
    (tmp_path / "dist/generated.py").write_text("print('generated')")
    _repository(
        tmp_path,
        f'\n[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"{pattern}" = ["print"]\n',
    )
    assert any("no authored Python" in error for error in check_repository(tmp_path))


@pytest.mark.parametrize(
    "settings",
    [
        '\n[tool.ruff.lint.per-file-ignores]\n"example.py" = ["print"]\n',
        '\n[tool.ruff.lint.per-file-ignores]\n#\n"example.py" = ["print"]\n',
    ],
)
def test_missing_or_empty_reason_comment_is_rejected(tmp_path: Path, settings: str) -> None:
    _repository(tmp_path, settings)
    assert any("reason comment" in error for error in check_repository(tmp_path))


def test_unrelated_comment_cannot_justify_later_exception(tmp_path: Path) -> None:
    _repository(
        tmp_path, '# This describes enabled rules.\nextend-select = ["T201"]\nignore = ["print"]\n'
    )
    assert any("reason comment" in error for error in check_repository(tmp_path))


def test_inline_table_cannot_bypass_reason_enforcement(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("""[tool.odfa11y.quality]
max-file-lines = 300
[tool.ruff]
lint = { select = ["ALL"], ignore = ["print"] }
""")
    (tmp_path / "example.py").write_text("print('visible')\n")
    assert any("explicit central tables" in error for error in check_repository(tmp_path))


@pytest.mark.parametrize(
    "directive",
    [
        "type: ignore",
        "type: ignore[invalid-assignment]",
        "ty: ignore[unresolved-reference]",
        "pyright: ignore",
        "mypy: ignore-errors",
        "nosec",
        "pyre-ignore",
        "pyre-fixme",
    ],
)
def test_inline_type_and_security_suppressions_are_rejected(tmp_path: Path, directive: str) -> None:
    _repository(tmp_path, "", f"value = 1  # {directive}\n")
    assert any("inline lint/format" in error for error in check_repository(tmp_path))


def test_suppression_spelling_in_string_is_content_not_configuration(tmp_path: Path) -> None:
    _repository(tmp_path, "", 'value = "# type: ignore # nosec"\n')
    assert check_repository(tmp_path) == []


def test_dash_named_python_file_is_analyzed_as_literal_path(tmp_path: Path) -> None:
    _repository(tmp_path, "", "value = 1\n")
    (tmp_path / "--exclude=example.py").write_text(
        'def answer() -> int:\n    return "wrong type"\n'
    )
    assert check_types(tmp_path) != 0


def test_dash_named_python_file_is_literal_in_unmasked_ruff_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository(
        tmp_path,
        "\n[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"
        '"--exclude=example.py" = ["print"]\n',
        "value = 1\n",
    )
    (tmp_path / "--exclude=example.py").write_text("print('visible')\n")
    monkeypatch.chdir(tmp_path)
    assert check_repository(Path()) == []


def test_scope_matching_is_case_sensitive_on_every_platform(tmp_path: Path) -> None:
    _repository(
        tmp_path,
        '\n[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"EXAMPLE.py" = ["print"]\n',
    )
    assert any("no authored Python" in error for error in check_repository(tmp_path))


@pytest.mark.parametrize(
    "settings",
    [
        (
            '# CLI output is stdout.\nignore = ["T201"]\n'
            "[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"
            '"example.py" = ["print"]\n'
        ),
        (
            "[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"
            '"example.py" = ["print", "T201"]\n'
        ),
    ],
)
def test_overlapping_masks_of_same_canonical_diagnostic_are_rejected(
    tmp_path: Path, settings: str
) -> None:
    _repository(tmp_path, settings)
    assert any("overlapping lint exception" in error for error in check_repository(tmp_path))


@pytest.mark.parametrize("pattern", ["*.py", "!tests/**", "{src,tests}/**", "src/*"])
def test_unsupported_globs_cannot_hide_broader_ruff_matching(tmp_path: Path, pattern: str) -> None:
    settings = (
        f'[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"{pattern}" = ["print"]\n'
    )
    _repository(tmp_path, settings)
    assert any("unsupported exception glob" in error for error in check_repository(tmp_path))


def test_basename_scope_covers_nested_files_as_ruff_does(tmp_path: Path) -> None:
    settings = (
        '[tool.ruff.lint.per-file-ignores]\n# CLI output is stdout.\n"example.py" = ["print"]\n'
    )
    _repository(tmp_path, settings, "value = 1\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "example.py").write_text("print('nested')\n")
    assert check_repository(tmp_path) == []


def test_disabled_type_rule_cannot_bypass_registry_or_canonical_type_gate(tmp_path: Path) -> None:
    _repository(
        tmp_path,
        '\n[tool.ty.rules]\nunresolved-import = "ignore"\n',
        "import nonexistent_module_for_policy_test\n",
    )
    assert any("type diagnostic suppression" in error for error in check_repository(tmp_path))
    assert check_types(tmp_path) != 0


@pytest.mark.parametrize(
    "settings",
    [
        '\n[tool.ruff]\nextend = "outside.toml"\n',
        '\n[tool.ruff.lint]\nselect = ["ALL"]\nexternal = ["CUSTOM"]\n',
        '\n[tool.ruff.lint]\nselect = ["F"]\n',
    ],
)
def test_hidden_configuration_authority_and_reduced_rule_selection_are_rejected(
    tmp_path: Path, settings: str
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.odfa11y.quality]\nmax-file-lines = 300\n" + settings
    )
    (tmp_path / "example.py").write_text("value = 1\n")
    assert check_repository(tmp_path)


def test_unmasked_probe_preserves_project_import_classification(tmp_path: Path) -> None:
    _repository(
        tmp_path,
        "\n[tool.ruff.lint.per-file-ignores]\n# Reviewed import layout.\n"
        '"example.py" = ["unsorted-imports"]\n',
        "import sys\n\nimport pytest\n\nfrom local_module import value\n",
    )
    (tmp_path / "local_module.py").write_text("value = 1\n")
    assert any(
        "unused lint exception: unsorted-imports" in error for error in check_repository(tmp_path)
    )


@pytest.mark.parametrize(
    "masked",
    [
        "# isort: skip_file\nimport sys\nimport os\n",
        "# isort: off\nimport sys\nimport os\n",
        "import sys  # isort: skip\nimport os\n",
    ],
)
def test_isort_action_comments_hide_real_ruff_findings_but_policy_rejects_them(
    tmp_path: Path, masked: str
) -> None:
    _repository(tmp_path, "", "import sys\nimport os\n")
    path = tmp_path / "example.py"
    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--isolated",
        "--select",
        "I001",
        "--ignore-noqa",
        "--output-format",
        "json",
        "--",
        str(path),
    ]
    control = run_bounded(command, timeout=20)
    assert control.returncode == 1
    assert {finding["code"] for finding in json.loads(control.stdout)} == {"I001"}
    path.write_text(masked)
    bypass = run_bounded(command, timeout=20)
    assert bypass.returncode == 0
    assert json.loads(bypass.stdout) == []
    assert any("inline lint/format" in error for error in check_repository(tmp_path))
