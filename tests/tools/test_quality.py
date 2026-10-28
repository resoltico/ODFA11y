# SPDX-License-Identifier: MPL-2.0
"""Reject family XML literals in orchestration, including aliases and hidden source."""

from __future__ import annotations

import ast
import re
lazy from pathlib import Path

import pytest

from tests.fixtures.paths import REPOSITORY
from tools.check_quality import authored_paths

# XML namespace prefixes whose elements belong to a document family, not to the ODF core.
FAMILY_PREFIXES = frozenset({
    "text",
    "table",
    "draw",
    "fo",
    "svg",
    "style",
    "presentation",
    "chart",
    "db",
    "form",
    "number",
    "dr3d",
    "anim",
    "smil",
    "math",
    "script",
})
FAMILY_NAME = re.compile(r"(?:^|[/@\[ (|])(?:" + "|".join(sorted(FAMILY_PREFIXES)) + r"):[A-Za-z]")
CORE_ROOT = ("src", "odfa11y")
CONTENT_ROOTS = {(*CORE_ROOT, "families"), (*CORE_ROOT, "content"), (*CORE_ROOT, "native")}


def _is_core(path: Path) -> bool:
    return path.parts[:2] == CORE_ROOT and path.parts[:3] not in CONTENT_ROOTS


def _check_core_purity(path: Path, source: str) -> list[str]:
    """Reject family-specific XML names in the ODF core.

    The core understands OpenDocument structure; families, shared content and native
    preflight primitives may name content vocabulary, while orchestration packages may not.
    Docstrings are prose and exempt.

    Returns
    -------
    list[str]
        One violation per family-specific qualified name or XPath literal in the core.

    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # Ruff reports invalid Python syntax.
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    qn_names = {"qn"} | {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == "qn"
    }
    errors = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        prefix = _family_qn_prefix(node, qn_names)
        if prefix is not None:
            errors.append(
                f"{path}:{line}: the ODF core must not name {prefix}: elements;"
                " that belongs in a family package"
            )
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and FAMILY_NAME.search(node.value)
        ):
            errors.append(
                f"{path}:{line}: the ODF core must not contain the family-specific name "
                f"{node.value!r}; that belongs in a family package"
            )
    return errors


def _family_qn_prefix(node: ast.AST, qn_names: set[str]) -> object | None:
    """Find a literal family prefix in ordinary qualified-name calls and import aliases.

    Returns
    -------
    object | None
        The family prefix when directly declared in the call, else None.

    """
    if not isinstance(node, ast.Call):
        return None
    named = (isinstance(node.func, ast.Name) and node.func.id in qn_names) or (
        isinstance(node.func, ast.Attribute) and node.func.attr == "qn"
    )
    if not named:
        return None
    first = (
        node.args[0]
        if node.args
        else next((keyword.value for keyword in node.keywords if keyword.arg == "prefix"), None)
    )
    return (
        first.value if isinstance(first, ast.Constant) and first.value in FAMILY_PREFIXES else None
    )


def _repository(tmp_path: Path) -> Path:
    return tmp_path


def check_repository(root: Path) -> list[str]:
    errors = []
    for path in authored_paths(root):
        relative = path.relative_to(root)
        if path.suffix == ".py" and _is_core(relative):
            errors.extend(_check_core_purity(relative, path.read_text(encoding="utf-8")))
    return errors


def test_project_has_no_family_xml_literals_in_orchestration() -> None:
    assert check_repository(REPOSITORY) == []


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


@pytest.mark.parametrize("owner", ["content", "native"])
def test_semantic_boundary_vocabulary_does_not_exempt_orchestration(
    tmp_path: Path,
    owner: str,
) -> None:
    root = _repository(tmp_path)
    _core_file(root, owner, "tables.py", source='value = "//table:table-row"\n')
    assert check_repository(root) == []
    _core_file(root, "pipeline", "run.py", source='value = "//table:table-row"\n')
    assert any("family" in error for error in check_repository(root))


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
