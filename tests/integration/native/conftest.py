# SPDX-License-Identifier: AGPL-3.0-only
"""Check validator-dependent integration prerequisites before native authoring or export."""

import pytest


@pytest.fixture
def required_verapdf(external_tool) -> None:
    external_tool("verapdf")
