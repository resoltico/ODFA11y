# SPDX-License-Identifier: MPL-2.0
"""Required native tools are identified once before execution and unused selections stay inert."""

from dataclasses import replace

import pytest

from odfa11y.application.tools import Tools
from odfa11y.errors import RemedyAction, ToolUnavailable
from odfa11y.tool_identity import ToolIdentity
from odfa11y.tool_timeout import Timeout
from tests.fixtures.native import export_settings, native_fakes, refusing


def test_required_tools_are_selected_once_and_share_the_validated_duration() -> None:
    calls = []

    def office(requested):
        calls.append(("office", requested))
        return "selected-office"

    def office_identity(executable, *, timeout):
        calls.append(("office-identity", executable, timeout))
        return ToolIdentity("LibreOffice", "26.8.0.3")

    def validator(requested):
        calls.append(("validator", requested))
        return "selected-validator"

    def validator_identity(name, executable, arguments, *, timeout):
        calls.append(("validator-identity", name, executable, arguments, timeout))
        return ToolIdentity("veraPDF", "1.30.0")

    native = replace(
        native_fakes(),
        locate=office,
        identify=office_identity,
        validator=validator,
        identify_validator=validator_identity,
    )
    selection = Tools(soffice="office", verapdf="validator", timeout=0.5)
    resolved = selection.resolve(libreoffice=True, verapdf=True, native_tools=native)
    assert [row[0] for row in calls] == [
        "office",
        "office-identity",
        "validator",
        "validator-identity",
    ]
    assert resolved.libreoffice is not None
    assert resolved.libreoffice.executable == "selected-office"
    assert resolved.verapdf is not None
    assert resolved.verapdf.executable == "selected-validator"
    assert resolved.timeout is selection.timeout
    assert calls[1][-1] is resolved.timeout
    assert calls[3][-1] is resolved.timeout


def test_unused_tool_paths_are_not_resolved() -> None:
    calls = []
    native = replace(native_fakes(), locate=refusing(calls), validator=refusing(calls))
    resolved = Tools(soffice="missing", verapdf="missing").resolve(native_tools=native)
    assert resolved.libreoffice is None
    assert resolved.verapdf is None
    assert not calls


@pytest.mark.parametrize("tool", ["libreoffice", "verapdf"])
def test_unidentifiable_required_tool_has_an_installation_remedy(tool: str) -> None:
    native = replace(
        native_fakes(),
        identify=lambda *_args, **_kwargs: ToolIdentity("LibreOffice", "unknown"),
        identify_validator=lambda *_args, **_kwargs: ToolIdentity("veraPDF", "unknown"),
    )
    with pytest.raises(ToolUnavailable) as failure:
        Tools().resolve(native_tools=native, **{tool: True})
    assert failure.value.exit_status == 3
    assert failure.value.remedy is not None
    assert failure.value.remedy.action is RemedyAction.INSTALL_TOOL


def test_validated_seconds_are_not_converted_back_to_unvalidated_inputs() -> None:
    seconds = Timeout(0.5)
    assert Timeout(seconds) is seconds
    assert Tools(timeout=seconds).timeout is seconds
    assert export_settings("writer_pdf_Export", timeout=seconds).timeout is seconds
