# SPDX-License-Identifier: AGPL-3.0-only
"""Each annotation rejects an independently specified invalid value."""

from dataclasses import dataclass, make_dataclass
from typing import Annotated, ClassVar

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from odfa11y.contracts import (
    Choices,
    Constraint,
    ExclusiveWhen,
    ItemCount,
    LanguageTag,
    Length,
    NonBlank,
    PathSafeName,
    Pattern,
    Range,
    RequireAny,
    XmlText,
    decode,
    encode,
    schema_for,
    validate,
)
from odfa11y.errors import InvalidOption, PlanError
from odfa11y.plans import parse_tables
from odfa11y.plans.fidelity import FidelityPolicy
from odfa11y.remediate.catalogue import registered_kinds


@pytest.mark.parametrize(
    ("value_type", "constraint", "valid", "invalid"),
    [
        (str, Pattern(r"^[a-z]+$"), "abc", "abc1"),
        (str, Length(2, 4), "abc", "abcde"),
        (str, Length(2), "ab", "a"),
        (str, Choices(("source", "pdf", "production")), "pdf", "verify"),
        (int, Range(1, 6), 2, 7),
        (int, Range(1), 1, 0),
        (str, NonBlank(), "Caption", "   "),
        (str, LanguageTag(), "en-GB", "en-u"),
        (str, XmlText(), "Caption", "illegal\x00character"),
        (str, PathSafeName(), "report.odt", "CON.txt"),
        (tuple[str, ...], ItemCount(1, 2), ("one",), ("one", "two", "three")),
        (tuple[str, ...], ItemCount(1), ("one",), ()),
    ],
)
def test_constraints_reject_values_in_decode_encode_and_schema(
    value_type: object, constraint: Constraint, valid: object, invalid: object
) -> None:
    contract = make_dataclass(
        "ConstrainedValue",
        [("value", Annotated.__getitem__((value_type, constraint)))],
        frozen=True,
    )
    decoded = decode(contract, {"value": valid})
    assert encode(decoded) == {"value": list(valid) if isinstance(valid, tuple) else valid}
    with pytest.raises(InvalidOption):
        decode(contract, {"value": invalid})
    with pytest.raises(InvalidOption):
        encode(contract(invalid))
    checker = FormatChecker()
    if name := getattr(constraint, "format_name", None):
        checker.checks(name)(lambda value: not constraint.problems(value))
    validator = Draft202012Validator(schema_for(contract), format_checker=checker)
    validator.validate({"value": list(valid) if isinstance(valid, tuple) else valid})
    with pytest.raises(ValidationError):
        validator.validate({"value": list(invalid) if isinstance(invalid, tuple) else invalid})


@dataclass(frozen=True)
class Alternative:
    title: Annotated[str | None, NonBlank(), XmlText()] = None
    decorative: bool | None = None
    __contract__: ClassVar[
        Annotated[
            object,
            RequireAny(("title", "decorative")),
            ExclusiveWhen("decorative", True, ("title",)),
        ]
    ]


def test_record_constraints_match_the_emitted_conditions() -> None:
    for value in ({}, {"title": "Meaning", "decorative": True}):
        with pytest.raises(InvalidOption):
            decode(Alternative, value)
        with pytest.raises(ValidationError):
            Draft202012Validator(schema_for(Alternative, input=True)).validate(value)
    assert decode(Alternative, {"decorative": True}) == Alternative(decorative=True)
    assert decode(Alternative, {"title": "Meaning"}) == Alternative(title="Meaning")


@dataclass(frozen=True)
class Count:
    value: int


@pytest.mark.parametrize("value", ["1", True, 1.0])
def test_integer_decode_never_coerces(value: object) -> None:
    with pytest.raises(InvalidOption):
        decode(Count, {"value": value})
    assert decode(Count, {"value": 1}) == Count(1)


def test_all_independent_field_problems_are_reported() -> None:
    contract = make_dataclass("Inputs", [("first", int), ("second", str)])
    with pytest.raises(InvalidOption) as caught:
        decode(contract, {"first": "bad", "second": 2, "unknown": True})
    message = str(caught.value)
    assert "first" in message
    assert "second" in message
    assert "unknown" in message


def test_validating_an_object_preserves_its_structure() -> None:
    value = Alternative(title="Meaning")
    validate(value)
    assert value.title == "Meaning"


@pytest.mark.parametrize("title", ["", "   "])
def test_graphic_titles_are_refused_at_plan_load(title: str) -> None:

    values = {
        "plan": {"schema_version": 1, "generator": "test", "source": {"sha256": "a" * 64}},
        "decisions": {
            "graphic.alternative": {
                "content/frame[name=Logo]": {"fingerprint": "b" * 16, "title": title}
            }
        },
    }
    with pytest.raises(PlanError, match="non-blank"):
        parse_tables(values, registered_kinds())


@pytest.mark.parametrize("setting", ["raster_tolerance", "ink_threshold"])
def test_may_change_refuses_ignored_settings(setting: str) -> None:

    with pytest.raises(InvalidOption, match=setting):
        decode(FidelityPolicy, {"pagination": "may-change", setting: 1})


def test_combined_constraints_are_all_retained_in_the_schema() -> None:
    annotation = Annotated[str, Pattern("A"), Pattern("B"), Pattern("C")]
    contract = make_dataclass("Letters", [("value", annotation)])
    for invalid in ("AB", "AC", "BC"):
        with pytest.raises(InvalidOption):
            decode(contract, {"value": invalid})
        with pytest.raises(ValidationError):
            Draft202012Validator(schema_for(contract)).validate({"value": invalid})
    assert encode(decode(contract, {"value": "ABC"})) == {"value": "ABC"}


@pytest.mark.parametrize(
    ("expected", "value", "path", "word"),
    [
        (int, "1", "plan.heading.level", "integer"),
        (bool, "true", "plan.text.enabled", "boolean"),
        (str, 7, "plan.metadata.title", "string"),
    ],
)
def test_scalar_mismatches_use_plain_expected_types(expected, value, path, word) -> None:
    with pytest.raises(PlanError) as caught:
        decode(expected, value, label=path, error=PlanError)
    text = str(caught.value)
    assert path in text
    assert word in text
    assert "<class" not in text
