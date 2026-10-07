# SPDX-License-Identifier: MPL-2.0
"""Negative controls for repository size and centralized lint policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.check_quality import check_repository


def _repository(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.odfa11y.quality]\nmax-file-lines = 300\n", encoding="utf-8"
    )
    return tmp_path


def test_file_limit_accepts_boundary_and_rejects_one_extra_line(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    source = root / "example.py"
    source.write_text("\n" * 300, encoding="utf-8")
    assert check_repository(root) == []
    source.write_text("\n" * 301, encoding="utf-8")
    assert any("301 lines" in error for error in check_repository(root))


@pytest.mark.parametrize(
    "directive", ["noqa: E501", "RUFF: noqa", "fmt: off", "pylint: disable=all"]
)
def test_inline_directives_are_rejected_in_hidden_directories(
    tmp_path: Path, directive: str
) -> None:
    root = _repository(tmp_path)
    directory = root / ".checks"
    directory.mkdir()
    (directory / "hidden.py").write_text(f"value = 1  # {directive}\n", encoding="utf-8")
    assert any("inline lint/format" in error for error in check_repository(root))


def test_directive_text_inside_strings_is_allowed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "example.py").write_text('value = "# noqa: E501"\n', encoding="utf-8")
    assert check_repository(root) == []


@pytest.mark.parametrize("filename", ["ruff.toml", ".ruff.toml", "pyproject.toml"])
def test_separate_lint_configuration_is_rejected(tmp_path: Path, filename: str) -> None:
    root = _repository(tmp_path)
    (root / "example.py").write_text("value = 1\n", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / filename).write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    assert any("configuration" in error for error in check_repository(root))


def test_empty_scan_is_rejected(tmp_path: Path) -> None:
    assert check_repository(_repository(tmp_path)) == ["No Python files were checked"]


def test_project_satisfies_policy() -> None:
    assert check_repository(Path(__file__).resolve().parents[1]) == []


@pytest.mark.parametrize(
    "settings",
    [
        '[tool.ruff.lint]\nignore = [\n"print",\n]\n',
        '[tool.ruff.lint]\nignore = ["print"]\n',
        '[tool.ruff.lint]\nignore=["print"]\n',
        '[tool.ruff.lint.per-file-ignores]\nexample=["print"]\n',
        '[tool.ruff.lint]\nextend-ignore = ["print"]\n',
        '[tool.ruff.lint.per-file-ignores]\n"example.py" = ["print"]\n',
    ],
)
def test_lint_exception_requires_a_reason(tmp_path: Path, settings: str) -> None:
    root = _repository(tmp_path)
    with (root / "pyproject.toml").open("a", encoding="utf-8") as stream:
        stream.write(settings)
    (root / "example.py").write_text("value = 1\n", encoding="utf-8")
    assert any("reason comment" in error for error in check_repository(root))


def test_per_file_ignores_for_missing_files_are_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "present.py").write_text("", encoding="utf-8")
    with (root / "pyproject.toml").open("a", encoding="utf-8") as stream:
        stream.write(
            "[tool.ruff.lint.per-file-ignores]\n# reason\n"
            '"present.py" = ["print"]\n# reason\n"gone.py" = ["print"]\n'
        )
    errors = check_repository(root)
    assert any("gone.py" in error for error in errors)
    assert not any("present.py" in error for error in errors)


def _core_file(root: Path, *parts: str, source: str) -> None:
    path = root.joinpath("src", "odfa11y", *parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    "source",
    [
        'from x import qn\nvalue = qn("text", "p")\n',
        'value = "//text:p"\n',
        'value = ".//table:table-row"\n',
        'value = "//*[@style:text-blinking]"\n',
    ],
)
def test_family_specific_names_are_rejected_in_the_core(tmp_path: Path, source: str) -> None:
    root = _repository(tmp_path)
    _core_file(root, "audit", "engine.py", source=source)
    assert any("family" in error for error in check_repository(root))


@pytest.mark.parametrize(
    "prefix", ["presentation", "chart", "db", "form", "dr3d", "math", "script"]
)
def test_specialized_content_names_are_rejected_in_orchestration(
    tmp_path: Path, prefix: str
) -> None:
    root = _repository(tmp_path)
    _core_file(
        root,
        "pipeline",
        "run.py",
        source=f"""from x import qn
qualified = qn("{prefix}", "content")
xpath = "//{prefix}:content"
""",
    )
    errors = check_repository(root)
    assert len(errors) == 2
    assert all("family" in error and prefix in error for error in errors)


def test_family_specific_names_are_allowed_in_a_family_package(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _core_file(root, "families", "text", "audit.py", source='value = "//text:p"\n')
    assert check_repository(root) == []


def test_core_prose_and_common_prefixes_are_allowed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    source = (
        '"""Mentions text:p only in prose."""\n'
        "from x import qn\n"
        'value = qn("office", "version")\n'
        'media = "application/vnd.oasis.opendocument.text"\n'
        'body = "office:text"\n'
    )
    _core_file(root, "odf", "kinds.py", source=source)
    assert check_repository(root) == []


def test_shared_content_vocabulary_is_allowed_but_does_not_exempt_orchestration(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _core_file(root, "content", "tables.py", source='value = "//table:table-row"\n')
    assert check_repository(root) == []
    _core_file(root, "pipeline", "run.py", source='value = "//table:table-row"\n')
    assert any("family" in error for error in check_repository(root))


@pytest.mark.parametrize("directory", ["build", "dist"])
def test_authored_nested_build_names_do_not_bypass_file_size_gate(
    tmp_path: Path, directory: str
) -> None:
    root = _repository(tmp_path)
    _core_file(root, directory, "authored.py", source="\n" * 301)
    assert any("301 lines" in error for error in check_repository(root))


def test_generated_root_build_outputs_are_excluded_but_ignored_authored_files_are_checked(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    for directory in ("build", "dist"):
        target = root / directory
        target.mkdir()
        (target / "generated.py").write_text("\n" * 301)
    (root / "authored.py").write_text("value = 1\n")
    assert check_repository(root) == []
    (root / ".gitignore").write_text(".authored/\n")
    ignored = root / ".authored"
    ignored.mkdir()
    (ignored / "source.py").write_text("\n" * 301)
    assert any(".authored/source.py" in error for error in check_repository(root))


@pytest.mark.parametrize(
    "source",
    [
        'from odfa11y.odf import qn as tag\nvalue = tag("text", "p")\n',
        'import odfa11y.odf as odf\nvalue = odf.qn("text", "p")\n',
        'from odfa11y.odf import qn\nvalue = qn(prefix="text", local="p")\n',
        'from odfa11y.odf import qn as tag\nvalue = tag(prefix="text", local="p")\n',
        'import odfa11y.odf as odf\nvalue = odf.qn(prefix="text", local="p")\n',
    ],
)
def test_ordinary_qualified_name_forms_cannot_bypass_family_boundaries(
    tmp_path: Path, source: str
) -> None:
    root = _repository(tmp_path)
    _core_file(root, "audit", "engine.py", source=source)
    assert any("text: elements" in error for error in check_repository(root))


def test_alias_detection_keeps_common_core_and_shared_content_vocabulary_valid(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _core_file(
        root,
        "audit",
        "engine.py",
        source='from x import qn as tag\nvalue = tag(prefix="office", local="body")\n',
    )
    _core_file(
        root, "content", "text.py", source='from x import qn as tag\nvalue = tag("text", "p")\n'
    )
    assert check_repository(root) == []


def test_normative_foreign_schema_namespace_is_structural_core_vocabulary(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _core_file(
        root,
        "odf",
        "schema.py",
        source='from x import NS\nnamespace = NS["math"]\nschema = "mathml/mathml3.rng"\n',
    )
    assert check_repository(root) == []
