# SPDX-License-Identifier: MPL-2.0
"""Decision parsing, templates and schemas share one strict registered answer contract."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import ClassVar, cast
lazy from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from odfa11y.decisions import Decision, DecisionKind, DecisionScope, OpenDecision, decode_answer
from odfa11y.errors import PlanError
from odfa11y.odf import Family
from odfa11y.plans import Plan, parse_tables, plan_schema, render_plan
from odfa11y.report import Location


@dataclass(frozen=True)
class Level:
    """A constrained answer independent of the codec implementation."""

    level: int = field(
        metadata={"schema": {"minimum": 1, "maximum": 10, "description": "Intended heading level."}}
    )


@dataclass(frozen=True)
class Metadata:
    """Optional answer fields still require a real answer."""

    title: str | None = field(default=None, metadata={"schema": {"pattern": r"\S"}})
    description: str | None = None
    required_any: ClassVar[tuple[str, ...]] = ("title", "description")


HEADING = DecisionKind(
    "heading.level", DecisionScope.TARGET, Level, frozenset({Family.TEXT}), "set_heading_levels"
)
METADATA = DecisionKind(
    "document.metadata", DecisionScope.DOCUMENT, Metadata, frozenset(Family), "set_metadata"
)
KINDS = {kind.id: kind for kind in [HEADING, METADATA]}


def header() -> dict[str, object]:
    return {"format": 1, "generator": "0.8.0", "source": {"sha256": "a" * 64}}


@pytest.mark.parametrize("value", [True, 0, 11, "2", 2.0, None])
def test_wrong_answer_types_and_ranges_are_rejected(value: object) -> None:
    with pytest.raises(PlanError, match=r"heading\.level"):
        decode_answer(Level, {"level": value}, "heading.level")


def test_unknown_and_missing_answer_fields_are_rejected() -> None:
    with pytest.raises(PlanError, match="Unknown"):
        decode_answer(Level, {"level": 2, "outline": 3}, "heading.level")
    with pytest.raises(PlanError, match="required"):
        decode_answer(Level, {}, "heading.level")
    with pytest.raises(PlanError, match="at least one"):
        decode_answer(Metadata, {}, "document.metadata")
    with pytest.raises(PlanError, match="syntax"):
        decode_answer(Metadata, {"title": "  "}, "document.metadata")


@pytest.mark.parametrize(
    "target",
    [
        "Heading",
        "content/heading[0]",
        "content/frame[name=raw name]",
        "content/frame[name=%ff]",
        "content//heading[1]",
    ],
)
def test_old_or_noncanonical_targets_are_rejected(target: str) -> None:
    with pytest.raises(PlanError, match=r"target|encoded"):
        Decision(HEADING, Location(target), "b" * 16, Level(2))


def test_targeted_answers_require_fingerprints_and_document_answers_refuse_targets() -> None:
    with pytest.raises(PlanError, match="fingerprint"):
        Decision(HEADING, Location("content/heading[1]"), None, Level(2))
    with pytest.raises(PlanError, match="document-scoped"):
        Decision(METADATA, Location("content/heading[1]"), None, Metadata(title="Title"))


def test_template_parse_answer_roundtrip_and_schema_agree() -> None:
    plan = parse_tables({"plan": header()}, KINDS)
    open_decision = OpenDecision(
        HEADING, Location("content/heading[1]"), "b" * 16, {"level": 3}, ("HEADING002",)
    )
    template = render_plan(plan.header, [open_decision])
    assert not parse_tables(tomllib.loads(template), KINDS).decisions
    answered = (
        template
        .replace("# [", "[")
        .replace("# fingerprint", "fingerprint")
        .replace("# level = 1", "level = 2")
    )
    values = tomllib.loads(answered)
    result = parse_tables(values, KINDS)
    assert result.decisions[0].answer_as(Level).level == 2
    assert result.decisions[0].target == Location("content/heading[1]")
    Draft202012Validator(plan_schema(KINDS)).validate(result.as_dict())
    values["decisions"]["heading.level"]["content/heading[1]"]["level"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(plan_schema(KINDS)).validate(values)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"document": {"title": "Old"}},
        {"plan": {"format": 1}},
        {"plan": header(), "decisions": {"missing.kind": {}}},
    ],
)
def test_header_and_kind_registry_are_mandatory(values: dict[str, object]) -> None:
    with pytest.raises(PlanError):
        parse_tables(values, KINDS)


def test_source_binding_refuses_another_source_without_explicit_rebind(tmp_path: Path) -> None:
    source, other = tmp_path / "source", tmp_path / "other"
    source.write_bytes(b"reviewed bytes")
    other.write_bytes(b"other bytes")
    plan = Plan.for_source(source)
    plan.verify_source(source)
    with pytest.raises(PlanError, match="digest mismatch"):
        plan.verify_source(other)
    plan.verify_source(other, rebind=True)


@pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, "A" * 64, "a" * 64 + "\n"])
def test_source_hash_is_exact_and_cannot_hide_a_trailing_newline(digest: str) -> None:
    binding = header()
    binding["source"] = {"sha256": digest}
    with pytest.raises(PlanError):
        parse_tables({"plan": binding}, KINDS)
    with pytest.raises(ValidationError):
        Draft202012Validator(plan_schema(KINDS)).validate({"plan": binding})


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1.0, 10**1000])
def test_policy_uses_the_same_strict_numeric_contract(value: object) -> None:
    with pytest.raises(PlanError, match="finite non-negative"):
        parse_tables({"plan": header(), "fidelity": {"raster_tolerance": value}}, KINDS)


def test_policy_numeric_equivalence_has_a_canonical_representation() -> None:
    integer = parse_tables({"plan": header(), "fidelity": {"raster_tolerance": 1}}, KINDS)
    floating = parse_tables({"plan": header(), "fidelity": {"raster_tolerance": 1.0}}, KINDS)
    assert integer.as_dict() == floating.as_dict()
    assert type(integer.fidelity.raster_tolerance) is float


@pytest.mark.parametrize("value", [1, "true", "false"])
def test_truthy_nonboolean_values_cannot_authorize_rebinding(tmp_path: Path, value: object) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"reviewed")
    plan = Plan.for_source(source)
    with pytest.raises(PlanError, match="explicit boolean"):
        plan.verify_source(source, rebind=cast("bool", value))
