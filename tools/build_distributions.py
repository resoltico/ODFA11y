# SPDX-License-Identifier: AGPL-3.0-only
"""Build from only declared distribution inputs, without ambient checkout metadata."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.source_inventory import distribution_sources

ROOT = Path(__file__).resolve().parents[1]


def build(source: Path, destination: Path) -> None:
    """Stage exact selected inputs before invoking the pinned isolated build backend."""
    with tempfile.TemporaryDirectory(prefix="odfa11y-build-inputs-") as temporary:
        staging = Path(temporary)
        for name, content in distribution_sources(source).items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(  # noqa: S603  Fixed build tool and exact selected inputs, no shell.
            [  # noqa: S607  Pinned build tool selected through PATH.
                "uv",
                "build",
                str(staging),
                "--python",
                sys.executable,
                "--out-dir",
                str(destination),
            ],
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
