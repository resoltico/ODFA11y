# SPDX-License-Identifier: MPL-2.0
"""Authoritative repository and test-resource locations for relocated checks."""

from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
REPOSITORY = TESTS.parent
