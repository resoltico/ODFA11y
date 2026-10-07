# SPDX-License-Identifier: MPL-2.0
"""Require justified, exact, effective exceptions in the authoritative Ruff policy."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w

if TYPE_CHECKING:
    from collections.abc import Iterable

SUPPRESSION_KEYS = ("ignore", "extend-ignore", "per-file-ignores", "extend-per-file-ignores")
INLINE_DIRECTIVE = re.compile(
    r"\b(?:noqa\b|ruff\s*:|fmt\s*:|pylint\s*:|isort\s*:|type\s*:\s*ignore\b|"
    r"ty\s*:|pyright\s*:|mypy\s*:|nosec\b|pyre-ignore\b|pyre-fixme\b)",
    re.IGNORECASE,
)


def analyzer_errors(config: dict[str, Any]) -> list[str]:
    """Reject configuration that bypasses the central analyzer policy.

    Returns
    -------
    list[str]
        Disabled diagnostics or configuration inherited from another authority.

    """
    tool = config.get("tool", {})
    ruff = tool.get("ruff", {})
    errors = []
    if "extend" in ruff or ruff.get("lint", {}).get("external"):
        errors.append("pyproject.toml: Ruff configuration and rule exceptions must be central")
    if ruff.get("lint", {}).get("select") != ["ALL"]:
        errors.append("pyproject.toml: the authored Python lint gate must select ALL")
    if any(level == "ignore" for level in tool.get("ty", {}).get("rules", {}).values()):
        errors.append("pyproject.toml: type diagnostic suppression is forbidden")
    return errors


def exception_errors(
    root: Path, source: str, config: dict[str, Any], paths: Iterable[Path]
) -> list[str]:
    """Check suppression reasons, discovery scope and actual unsuppressed diagnostics.

    Returns
    -------
    list[str]
        Relative-path policy errors, without external tool diagnostic text.

    """
    lint = config.get("tool", {}).get("ruff", {}).get("lint", {})
    entries = _entries(lint)
    errors = analyzer_errors(config)
    if not entries:
        return errors
    errors.extend(_reason_errors(source, lint))
    files = [path for path in paths if path.suffix == ".py"]
    matches: dict[str, list[Path]] = {}
    for pattern, _ in entries:
        if pattern is None:
            continue
        selected = _scope_files(root, files, pattern)
        if selected is None:
            errors.append(
                f"pyproject.toml: unsupported exception glob: {pattern}; "
                "use a literal relative path or directory/**"
            )
        elif not selected:
            errors.append(
                f"pyproject.toml: per-file ignore matches no authored Python file: {pattern}"
            )
        else:
            matches[pattern] = selected
    if errors:
        return errors
    try:
        catalogue, findings = _probe(root, config, files)
    except OSError, ValueError, subprocess.TimeoutExpired:
        return ["pyproject.toml: cannot verify lint exceptions with the locked Ruff analyzer"]
    codes = {key: row["code"] for row in catalogue for key in (row["code"], row["name"])}
    scopes: dict[str | None, set[str]] = {
        pattern: {str(path.resolve()) for path in selected} for pattern, selected in matches.items()
    }
    scopes[None] = {str(path.resolve()) for path in files}
    return _effect_errors(entries, scopes, codes, findings)


def _scope_files(root: Path, files: list[Path], pattern: str) -> list[Path] | None:
    # Ruff also matches literal basename patterns anywhere in the authored tree.
    directory = pattern.removesuffix("/**")
    if any(char in directory for char in "*?[]{}!\\"):
        return None
    if pattern.endswith("/**"):
        return [
            path for path in files if path.relative_to(root).as_posix().startswith(directory + "/")
        ]
    return [
        path
        for path in files
        if path.relative_to(root).as_posix() == pattern or path.name == pattern
    ]


def _effect_errors(
    entries: list[tuple[str | None, list[str]]],
    scopes: dict[str | None, set[str]],
    codes: dict[str, str],
    findings: list[dict],
) -> list[str]:
    errors = []
    covered: dict[str, set[int]] = {}
    by_rule: dict[str, list[tuple[int, str]]] = {}
    for index, row in enumerate(findings):
        by_rule.setdefault(row["code"], []).append((index, row["filename"]))
    for pattern, selectors in entries:
        for selector in selectors:
            scope = pattern or "global"
            if selector not in codes:
                errors.append(
                    f"pyproject.toml: {scope}: exception must select one exact Ruff rule: "
                    f"{selector}"
                )
                continue
            code = codes[selector]
            observed = {
                index for index, filename in by_rule.get(code, []) if filename in scopes[pattern]
            }
            if not observed:
                errors.append(f"pyproject.toml: {scope}: unused lint exception: {selector}")
            elif observed & covered.get(code, set()):
                errors.append(f"pyproject.toml: {scope}: overlapping lint exception: {selector}")
            covered.setdefault(code, set()).update(observed)
    return errors


def _entries(lint: dict[str, Any]) -> list[tuple[str | None, list[str]]]:
    entries = [(None, lint[key]) for key in SUPPRESSION_KEYS[:2] if lint.get(key)]
    entries.extend(
        (pattern, selectors)
        for key in SUPPRESSION_KEYS[2:]
        for pattern, selectors in lint.get(key, {}).items()
        if selectors
    )
    return entries


def _reason_errors(source: str, lint: dict[str, Any]) -> list[str]:
    errors = []
    section = ""
    in_ignores = False
    reason = False
    seen: set[tuple[str, str]] = set()
    for number, raw in enumerate(source.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("["):
            section, reason = line, False
        elif line.startswith("#"):
            reason = bool(line.removeprefix("#").strip())
        elif in_ignores:
            if line == "]":
                in_ignores = False
            elif line and not reason:
                errors.append(_reason_error(number))
            reason = False
        else:
            declaration = _declaration(line, section)
            if declaration is not None:
                seen.add(declaration)
                in_ignores = declaration[0] == "lint" and not line.endswith("]")
                has_values = not in_ignores or bool(line.split("[", 1)[1].strip())
                if has_values and not reason:
                    errors.append(_reason_error(number))
            reason = False
    if _expected_declarations(lint) - seen:
        errors.append(
            "pyproject.toml: lint exceptions require explicit central tables "
            "and a preceding reason comment"
        )
    return errors


def _declaration(line: str, section: str) -> tuple[str, str] | None:
    if re.match(r"(?:ignore|extend-ignore)\s*=\s*\[", line) and section == "[tool.ruff.lint]":
        return "lint", line.split("=", 1)[0].strip()
    if "=" in line and section in {
        "[tool.ruff.lint.per-file-ignores]",
        "[tool.ruff.lint.extend-per-file-ignores]",
    }:
        key = re.match(r'("(?:[^"\\]|\\.)*"|\'[^\']*\'|[A-Za-z0-9_-]+)\s*=', line)
        if key is None:
            return None
        pattern = next(iter(tomllib.loads(f"{key[1]} = 0")))
        return section.removeprefix("[tool.ruff.lint.").removesuffix("]"), pattern
    return None


def _expected_declarations(lint: dict[str, Any]) -> set[tuple[str, str]]:
    return {("lint", key) for key in SUPPRESSION_KEYS[:2] if lint.get(key)} | {
        (key, pattern)
        for key in SUPPRESSION_KEYS[2:]
        for pattern, selectors in lint.get(key, {}).items()
        if selectors
    }


def _reason_error(number: int) -> str:
    return f"pyproject.toml:{number}: lint exception requires a preceding reason comment"


def _probe(root: Path, config: dict[str, Any], files: list[Path]) -> tuple[list[dict], list[dict]]:
    unmasked = copy.deepcopy(config)
    ruff = unmasked["tool"]["ruff"]
    ruff["src"] = [str((root / path).resolve()) for path in ruff.get("src", [".", "src"])]
    lint = ruff["lint"]
    for key in SUPPRESSION_KEYS:
        lint.pop(key, None)
    catalogue = _ruff_json(root, ["rule", "--all", "--output-format", "json"])
    with tempfile.TemporaryDirectory(prefix="odfa11y-lint-policy-") as scratch:
        path = Path(scratch) / "pyproject.toml"
        path.write_text(tomli_w.dumps(unmasked), encoding="utf-8")
        findings = _ruff_json(
            root,
            [
                "check",
                "--config",
                str(path),
                "--ignore-noqa",
                "--output-format",
                "json",
                "--",
                *(str(file) for file in files),
            ],
        )
    return catalogue, findings


def _ruff_json(root: Path, arguments: list[str]) -> list[dict]:
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", *arguments],
        cwd=root,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode not in {0, 1}:
        message = "Ruff exception probe failed"
        raise ValueError(message)
    return json.loads(completed.stdout)
