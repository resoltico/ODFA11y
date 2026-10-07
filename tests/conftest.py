# SPDX-License-Identifier: MPL-2.0
"""Configure Hypothesis for deterministic, bounded runs."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, settings

if TYPE_CHECKING:
    from collections.abc import Callable

settings.register_profile(
    "default",
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("default")


@pytest.fixture
def external_tool() -> Callable[..., str]:
    """Locate an external application, skipping locally but failing where it is required.

    Returns
    -------
    Callable[..., str]
        A locator returning the first executable found among the given names.

    """

    def locate(*names: str) -> str:
        for name in names:
            if found := shutil.which(name):
                return found
        message = f"{names[0]} is not installed"
        if os.environ.get("ODFA11Y_REQUIRE_INTEGRATION"):
            pytest.fail(message)
        pytest.skip(message)

    return locate
