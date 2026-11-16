# SPDX-License-Identifier: MPL-2.0
"""Required native tools are identified once before execution and unused selections stay inert."""

import json
from dataclasses import replace

import pytest

from odfa11y import batch
from odfa11y.application.tools import Tools
from odfa11y.errors import RemedyAction, ToolUnavailable
from odfa11y.status import Profile
from odfa11y.tool_identity import ToolIdentity
from odfa11y.tool_timeout import Timeout
from tests.batch.test_batch import write_batch_file
from tests.fixtures.native import export_settings, native_fakes, refusing
from tests.fixtures.plans import plan_header
from tests.fixtures.writer import make_minimal_odt


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


def _record_tool_resolution(calls):
    native = native_fakes()

    def locate(requested):
        calls.append("locate")
        return native.locate(requested)

    def identify(*args, **kwargs):
        calls.append("identify")
        return native.identify(*args, **kwargs)

    def validator(requested):
        calls.append("validator")
        return native.validator(requested)

    def identify_validator(*args, **kwargs):
        calls.append("identify-validator")
        return native.identify_validator(*args, **kwargs)

    return replace(
        native,
        locate=locate,
        identify=identify,
        validator=validator,
        identify_validator=identify_validator,
    )


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("source", []),
        ("pdf", ["locate", "identify"]),
        ("production", ["locate", "identify", "validator", "identify-validator"]),
    ],
)
def test_batch_resolves_required_tools_once_for_all_items(tmp_path, profile, expected) -> None:

    source = make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text(plan_header(source))
    batch_file = write_batch_file(
        tmp_path, [("one", "doc.odt", "plan.toml"), ("two", "doc.odt", "plan.toml")]
    )
    calls = []
    record = batch(
        batch_file,
        tmp_path / "out",
        profile=Profile(profile),
        native_tools=_record_tool_resolution(calls),
    )
    assert record.exit_status == 0
    assert record.profile == Profile(profile)
    assert calls == expected
    for item in ("one", "two"):
        published = json.loads((tmp_path / "out" / item / "run.json").read_text())
        assert published["profile"] == profile
        if profile != "source":
            assert published["toolchain"]["libreoffice"]["version"] == "26.8.0.3"
        if profile == "production":
            assert published["toolchain"]["verapdf"]["version"] == "test"


def test_batch_retains_item_preparation_failures_without_retrying_absent_tools(tmp_path) -> None:

    source = make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text(plan_header(source))
    (tmp_path / "bad.toml").write_text("[unknown]\nvalue = 1\n")
    batch_file = write_batch_file(
        tmp_path,
        [
            ("bad", "doc.odt", "bad.toml"),
            ("one", "doc.odt", "plan.toml"),
            ("two", "doc.odt", "plan.toml"),
        ],
    )
    calls = []

    def absent(requested):
        calls.append("validator")
        message = "veraPDF unavailable"
        raise ToolUnavailable(message)

    record = batch(
        batch_file,
        tmp_path / "out",
        profile=Profile.PRODUCTION,
        native_tools=replace(_record_tool_resolution(calls), validator=absent),
    )
    assert [item.exit_status for item in record.items] == [4, 3, 3]
    assert calls == ["locate", "identify", "validator"]
    assert record.exit_status == 3
    assert all(item.error is not None and item.evidence is None for item in record.items)
    assert {path.name for path in (tmp_path / "out").iterdir()} == {"batch.json"}
