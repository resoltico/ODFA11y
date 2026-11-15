# SPDX-License-Identifier: MPL-2.0
"""Verify independent package imports and the presentation-free root API."""

import subprocess
import sys

import pytest

from tests.fixtures.paths import REPOSITORY

ROOT = REPOSITORY


@pytest.mark.parametrize(
    "module",
    [
        "odfa11y.pdf.fidelity",
        "odfa11y.native.probes",
        "odfa11y.concepts",
        "odfa11y.odf.styles",
        "odfa11y.run",
    ],
)
def test_package_initializers_allow_independent_import_order(module: str) -> None:
    result = subprocess.run(  # noqa: S603  Module names are fixed test parameters and Python is explicit.
        [
            sys.executable,
            "-c",
            f"import {module}; import sys; assert 'odfa11y.cli' not in sys.modules",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout
