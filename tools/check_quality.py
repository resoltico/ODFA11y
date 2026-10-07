# SPDX-License-Identifier: MPL-2.0
"""Enforce file-size limits and centralized lint policy across authored Python."""

from __future__ import annotations

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lint_policy import INLINE_DIRECTIVE, analyzer_errors, exception_errors

if TYPE_CHECKING:
    from collections.abc import Iterator

GENERATED_DIRECTORIES = {".git", ".venv", "__pycache__", ".ruff_cache"}
ROOT_BUILD_DIRECTORIES = {"build", "dist"}
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
CONTENT_ROOTS = {(*CORE_ROOT, "families"), (*CORE_ROOT, "content")}


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
    paths = list(authored_paths(root))
    errors = exception_errors(root, config_text, config, paths)
    files_checked = 0
    for path in paths:
        relative = path.relative_to(root)
        if path.name in {"ruff.toml", ".ruff.toml"}:
            errors.append(f"{relative}: Ruff configuration belongs in the root pyproject.toml")
        if path.name == "pyproject.toml" and path != root / "pyproject.toml":
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


def authored_paths(root: Path) -> Iterator[Path]:
    """Yield authored files, including hidden/ignored paths, outside generated resources.

    Yields
    ------
    Path
        Files in the shared policy and analyzer discovery scope.

    """
    for directory, dirs, files in root.walk():
        excluded = GENERATED_DIRECTORIES | (ROOT_BUILD_DIRECTORIES if directory == root else set())
        dirs[:] = [name for name in dirs if name not in excluded]
        yield from (directory / name for name in files)


def check_types(root: Path) -> int:
    """Run the locked type checker on explicit authored Python paths.

    Returns
    -------
    int
        The analyzer's exit status; one for invalid configuration, empty discovery
        or unavailable execution.

    """
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        sys.stderr.write("Cannot read authoritative analyzer configuration\n")
        return 1
    errors = analyzer_errors(config)
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
        return 1
    files = sorted(
        path.relative_to(root).as_posix() for path in authored_paths(root) if path.suffix == ".py"
    )
    if not files:
        sys.stderr.write("No Python files were checked\n")
        return 1
    try:
        return subprocess.run(
            [sys.executable, "-m", "ty", "check", "--", *files], cwd=root, shell=False, check=False
        ).returncode
    except OSError:
        sys.stderr.write("Cannot execute the type checker\n")
        return 1


def _is_core(path: Path) -> bool:
    return path.parts[:2] == CORE_ROOT and path.parts[:3] not in CONTENT_ROOTS


def _check_core_purity(path: Path, source: str) -> list[str]:
    """Reject family-specific XML names in the ODF core.

    The core understands OpenDocument structure; families and shared content primitives may name
    content vocabulary, while orchestration packages may not. Docstrings are prose and exempt.

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--types", action="store_true", help="Type-check every authored Python file."
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.types:
        return check_types(root)
    errors = check_repository(root)
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
    else:
        sys.stdout.write("File sizes and centralized lint policy passed.\n")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
