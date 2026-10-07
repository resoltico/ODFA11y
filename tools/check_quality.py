# SPDX-License-Identifier: MPL-2.0
"""Enforce file-size limits and centralized lint policy across authored Python."""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
import tomllib
from pathlib import Path
from typing import Any

GENERATED_DIRECTORIES = {".git", ".venv", "build", "dist", "__pycache__", ".ruff_cache"}
INLINE_DIRECTIVE = re.compile(r"\b(?:noqa\b|ruff\s*:|fmt\s*:|pylint\s*:)", re.IGNORECASE)
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
    "form",
    "number",
    "dr3d",
    "anim",
    "smil",
    "math",
})
FAMILY_NAME = re.compile(r"(?:^|[/@\[ (|])(?:" + "|".join(sorted(FAMILY_PREFIXES)) + r"):[A-Za-z]")
CORE_ROOT = ("src", "odfa11y")
FAMILY_ROOT = (*CORE_ROOT, "families")


def check_repository(root: Path) -> list[str]:
    """Check every authored Python file, including hidden directories.

    Returns
    -------
    list[str]
        Violations with relative paths; an empty list means policy compliance.

    """
    config_text = (root / "pyproject.toml").read_text(encoding="utf-8")
    config = tomllib.loads(config_text)
    limit = config["tool"]["odfa11y"]["quality"]["max-file-lines"]
    errors = _exception_reasons(config_text)
    errors.extend(_stale_ignores(root, config))
    files_checked = 0
    for directory, dirs, files in root.walk():
        dirs[:] = [name for name in dirs if name not in GENERATED_DIRECTORIES]
        for name in files:
            path = directory / name
            relative = path.relative_to(root)
            if name in {"ruff.toml", ".ruff.toml"}:
                errors.append(f"{relative}: Ruff configuration belongs in the root pyproject.toml")
            if name == "pyproject.toml" and path != root / name:
                nested = tomllib.loads(path.read_text(encoding="utf-8"))
                if "ruff" in nested.get("tool", {}):
                    errors.append(f"{relative}: nested Ruff configuration is forbidden")
            if path.suffix != ".py":
                continue
            files_checked += 1
            source = path.read_text(encoding="utf-8")
            errors.extend(_check_source(relative, source, limit))
            if _is_core(relative):
                errors.extend(_check_core_purity(relative, source))
    if not files_checked:
        errors.append("No Python files were checked")
    return errors


def _is_core(path: Path) -> bool:
    return path.parts[:2] == CORE_ROOT and path.parts[:3] != FAMILY_ROOT


def _check_core_purity(path: Path, source: str) -> list[str]:
    """Reject family-specific XML names in the ODF core.

    The core understands OpenDocument structure; only a family package may name that
    family's elements. Docstrings are prose and exempt.

    Returns
    -------
    list[str]
        One violation per family-specific qualified name or XPath literal in the core.

    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # reported by the tokenizer check
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    errors = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        prefix = _family_qn_prefix(node)
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


def _family_qn_prefix(node: ast.AST) -> object | None:
    """Find the family prefix in a ``qn("<prefix>", ...)`` call.

    Returns
    -------
    object | None
        The prefix when the node is such a call, else None.

    """
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args):
        return None
    first = node.args[0]
    named = node.func.id == "qn" and isinstance(first, ast.Constant)
    return first.value if named and first.value in FAMILY_PREFIXES else None


def _stale_ignores(root: Path, config: dict[str, Any]) -> list[str]:
    lint = config.get("tool", {}).get("ruff", {}).get("lint", {})
    return [
        f"pyproject.toml: per-file ignore matches no file: {pattern}"
        for table in ("per-file-ignores", "extend-per-file-ignores")
        for pattern in lint.get(table, {})
        if not any(root.glob(pattern))
    ]


def _exception_reasons(source: str) -> list[str]:
    errors = []
    section = ""
    in_ignores = False
    reason = False
    for number, raw in enumerate(source.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("["):
            section = line
            reason = False
        elif line.startswith("#"):
            reason = bool(line.removeprefix("#").strip())
        elif re.match(r"(?:ignore|extend-ignore)\s*=\s*\[", line) and section == "[tool.ruff.lint]":
            if line.split("[", 1)[1].strip() not in {"", "]"} and not reason:
                errors.append(
                    f"pyproject.toml:{number}: lint exception requires a preceding reason comment"
                )
            in_ignores = not line.endswith("]")
            reason = False
        elif in_ignores and line == "]":
            in_ignores = False
        elif ("=" in line or line.startswith(('"', "'"))) and (
            in_ignores
            or section
            in {
                "[tool.ruff.lint.per-file-ignores]",
                "[tool.ruff.lint.extend-per-file-ignores]",
            }
        ):
            if not reason:
                errors.append(
                    f"pyproject.toml:{number}: lint exception requires a preceding reason comment"
                )
            reason = False
    return errors


def _check_source(path: Path, source: str, limit: int) -> list[str]:
    errors = []
    lines = len(source.splitlines())
    if lines > limit:
        errors.append(
            f"{path}: {lines} lines exceeds the {limit}-line limit; split by responsibility"
        )
    try:
        errors.extend(
            f"{path}:{token.start[0]}: inline lint/format directive is forbidden"
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.COMMENT and INLINE_DIRECTIVE.search(token.string)
        )
    except (tokenize.TokenError, IndentationError) as exc:
        errors.append(f"{path}: cannot tokenize Python: {exc}")
    return errors


def main() -> int:
    """Check the repository and report failures on stderr.

    Returns
    -------
    int
        Zero on policy compliance, or one when any violation is found.

    """
    root = Path(__file__).resolve().parents[1]
    errors = check_repository(root)
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
    else:
        sys.stdout.write("File sizes and centralized lint policy passed.\n")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
