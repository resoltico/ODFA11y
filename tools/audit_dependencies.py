# SPDX-License-Identifier: MPL-2.0
"""Audit the locked dependency set with the existing strict hashed-input policy."""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="odfa11y-dependency-audit-") as temporary:
        requirements = Path(temporary) / "requirements.txt"
        subprocess.run(  # noqa: S603  Fixed CI qualification commands; no shell or document-controlled executable.
            [  # noqa: S607  Fixed CI qualification commands; no shell or document-controlled executable.
                "uv",
                "export",
                "--locked",
                "--group",
                "audit",
                "--no-emit-project",
                "--output-file",
                str(requirements),
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        result = subprocess.run(  # noqa: S603  Fixed CI qualification commands; no shell or document-controlled executable.
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--strict",
                "--require-hashes",
                "--disable-pip",
                "-r",
                str(requirements),
            ],
            cwd=ROOT,
            check=False,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
