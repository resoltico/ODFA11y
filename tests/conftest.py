# SPDX-License-Identifier: MPL-2.0
"""Configure Hypothesis for deterministic, bounded runs."""

import os
import shutil
lazy from collections.abc import Callable

import pytest
from hypothesis import HealthCheck, settings

from odfa11y.application.native import NativeTools
from tests.fixtures.native import native_fakes

settings.register_profile(
    "required",
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("smoke", parent=settings.get_profile("required"), max_examples=5)
settings.load_profile("required")


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


@pytest.fixture
def native_tools() -> NativeTools:
    """Supply explicit native operations to a test that requests the seam."""
    return native_fakes()
