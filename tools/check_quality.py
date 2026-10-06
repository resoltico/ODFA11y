# SPDX-License-Identifier: MPL-2.0
"""Enforce file-size limits and centralized lint policy across authored Python."""

from __future__ import annotations

import io
import re
import sys
import tokenize
import tomllib
from pathlib import Path

GENERATED_DIRECTORIES = {".git", ".venv", "build", "dist", "__pycache__", ".ruff_cache"}
INLINE_DIRECTIVE = re.compile(r"\b(?:noqa\b|ruff\s*:|fmt\s*:|pylint\s*:)", re.IGNORECASE)


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
            errors.extend(_check_source(relative, path.read_text(encoding="utf-8"), limit))
    if not files_checked:
        errors.append("No Python files were checked")
    return errors


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
