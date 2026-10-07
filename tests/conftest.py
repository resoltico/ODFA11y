# SPDX-License-Identifier: MPL-2.0
"""Configure Hypothesis for deterministic, bounded runs."""

from __future__ import annotations

from hypothesis import HealthCheck, settings

settings.register_profile(
    "default",
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("default")
