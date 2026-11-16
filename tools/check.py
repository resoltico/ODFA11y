# SPDX-License-Identifier: MPL-2.0
"""Run repository checks with the restored development environment."""

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "lint",
    "types",
    "boundaries",
    "reference",
    "unit",
    "integration",
    "build",
    "release",
    "audit",
)


def commands(stage: str, *, notes_output: Path | None = None) -> tuple[list[str], ...]:
    """Return the commands owned by a check stage."""
    python = sys.executable
    match stage:
        case "lint":
            return (
                [python, "-m", "ruff", "check", "."],
                [python, "-m", "ruff", "format", "--check", "."],
            )
        case "audit":
            return ([python, "-m", "tools.audit_dependencies"],)
        case "types":
            return ([python, "-m", "ty", "check"],)
        case "boundaries":
            return ([python, "-m", "tach", "check"], [python, "-m", "tach", "check-external"])
        case "reference":
            return ([python, "-m", "tools.generate_reference", "--check"],)
        case "unit":
            return ([python, "-m", "pytest", "--ignore=tests/integration", "-n", "auto", "--cov"],)
        case "integration":
            return (
                [python, "-m", "pytest", "tests/integration", "-n", "2", "--max-worker-restart=0"],
            )
        case "build":
            return ([python, "-m", "tools.build_distributions"],)
        case "release":
            project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
                "project"
            ]
            return (
                [
                    python,
                    "-m",
                    "tools.check_release",
                    f"v{project['version']}",
                    "dist",
                    *(["--notes-output", str(notes_output)] if notes_output is not None else []),
                ],
                [python, "-m", "tools.qualify_build", "dist"],
            )
        case _:
            raise ValueError(stage)


def main() -> int:
    """Run requested stages in order, stopping at the first failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stages", nargs="+", choices=(*STAGES, "all"), help="Checks to run, in order."
    )
    parser.add_argument(
        "--notes-output", type=Path, help="Write changelog notes during release qualification."
    )
    args = parser.parse_args()
    stages = [stage for name in args.stages for stage in (STAGES if name == "all" else (name,))]
    for stage in stages:
        for command in commands(stage, notes_output=args.notes_output):
            sys.stderr.write(f"{stage}: {' '.join(command)}\n")
            try:
                result = subprocess.run(command, cwd=ROOT, check=False, shell=False)  # noqa: S603  Trusted tool arguments.
            except OSError as error:
                sys.stderr.write(f"Cannot run {stage}: {error}\n")
                return 1
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
