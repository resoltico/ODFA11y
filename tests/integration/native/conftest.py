# SPDX-License-Identifier: MPL-2.0
"""Check validator-dependent integration prerequisites before native authoring or export."""

import pytest


@pytest.fixture
def required_verapdf(external_tool) -> None:
    external_tool("verapdf")
