# SPDX-License-Identifier: MPL-2.0
"""Core vocabulary and outcomes keep acceptance policy independent of presentation."""

import importlib
from enum import EnumType

import pytest

from odfa11y.errors import InvalidOption, OdfA11yError, RemedyAction
from odfa11y.report import Report, ReportKind
from odfa11y.rules import registry as rules
from odfa11y.status import (
    ExitStatus,
    NotApplicable,
    Profile,
    Skipped,
    SkipReason,
    combine_statuses,
    gate_outcome,
)
from tests.fixtures.paths import REPOSITORY


def test_every_core_enum_member_has_a_meaning() -> None:
    seen = set()
    for path in (REPOSITORY / "src/odfa11y").rglob("*.py"):
        if path.name == "__main__.py" or "cli" in path.parts:
            continue
        name = ".".join(path.relative_to(REPOSITORY / "src").with_suffix("").parts)
        module = importlib.import_module(name.removesuffix(".__init__"))
        seen.update(
            value
            for value in vars(module).values()
            if isinstance(value, EnumType) and value.__module__.startswith("odfa11y.")
        )
    assert seen
    for enum_type in seen:
        for member in enum_type:
            assert isinstance(member.meaning, str), (enum_type, member)
            assert member.meaning.endswith("."), (enum_type, member)


def test_skipped_and_inapplicable_stages_do_not_change_exit_status() -> None:
    outcomes = [Skipped(SkipReason.PROFILE), NotApplicable("The family has no PDF export.")]
    assert combine_statuses([ExitStatus.ERRORS, *(o.exit_status(True) for o in outcomes)]) == 2
    assert combine_statuses(o.exit_status(True) for o in outcomes) == 0


def test_warning_only_report_respects_the_selected_profile() -> None:
    report = Report(ReportKind.ODF, "candidate.odt")
    report.raise_(rules.HEADING003)
    assert gate_outcome(report, strict=Profile.PRODUCTION.strict).exit_status(True) == 1
    assert gate_outcome(report, strict=Profile.PDF.strict).exit_status(False) == 0


def test_unknown_profile_is_a_usage_error() -> None:
    with pytest.raises(InvalidOption) as caught:
        Profile.parse("verify")
    assert caught.value.exit_status == 4


def test_errors_declare_distinct_codes_and_statuses() -> None:
    errors = importlib.import_module("odfa11y.errors")
    classes = [
        value
        for value in vars(errors).values()
        if isinstance(value, type) and issubclass(value, OdfA11yError)
    ]
    assert len({error.code for error in classes}) == len(classes)
    assert all(isinstance(error.exit_status, ExitStatus) for error in classes)
    assert RemedyAction.EMBED_RESOURCE.meaning


def test_profile_comparison_uses_assurance_order() -> None:
    assert Profile.SOURCE < Profile.PDF < Profile.PRODUCTION
    assert Profile.PRODUCTION >= Profile.PDF >= Profile.SOURCE
    assert sorted([Profile.PRODUCTION, Profile.SOURCE, Profile.PDF]) == [
        Profile.SOURCE,
        Profile.PDF,
        Profile.PRODUCTION,
    ]
