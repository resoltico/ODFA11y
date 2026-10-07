# SPDX-License-Identifier: MPL-2.0
"""Missing native tools must fail required integration, including in distributed runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


def test_required_integration_rejects_an_unavailable_tool(
    monkeypatch: pytest.MonkeyPatch, external_tool: Callable[..., str]
) -> None:
    monkeypatch.setenv("ODFA11Y_REQUIRE_INTEGRATION", "1")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(pytest.fail.Exception, match="missing-native-tool is not installed"):
        external_tool("missing-native-tool")


def test_optional_integration_records_an_unavailable_tool_as_a_skip(
    monkeypatch: pytest.MonkeyPatch, external_tool: Callable[..., str]
) -> None:
    monkeypatch.delenv("ODFA11Y_REQUIRE_INTEGRATION", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(pytest.skip.Exception, match="missing-native-tool is not installed"):
        external_tool("missing-native-tool")
