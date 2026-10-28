# SPDX-License-Identifier: MPL-2.0
"""Bound plan files validate registered answers and compile in dependency order."""

from __future__ import annotations

from pathlib import Path

import pytest

from odfa11y.decisions.answers import DocumentMetadataAnswer
from odfa11y.errors import PlanError
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument
from odfa11y.plans import load_plan
from odfa11y.remediation.planning import compile_operations

from .fixtures import make_minimal_odt

HEADER = '[plan]\nformat = 1\ngenerator = "0.8.0"\nsource.sha256 = "' + "a" * 64 + '"\n'
FULL = (
    HEADER
    + """
[decisions."text.remove_spacers"]
enabled = true
[decisions."document.metadata"]
title = "Decision"
description = "Decision letter"
language = "en-GB"
[decisions."document.odf_version"]
version = "1.3"
[decisions."text.linkify_addresses"]
enabled = true
[decisions."table.headers"."content/table[name=Data]"]
rows = 1
fingerprint = "0123456789abcdef"
[decisions."graphic.alternative"."content/frame[name=Logo]"]
title = "Organisation"
description = "Organisation logo."
fingerprint = "fedcba9876543210"
[decisions."text.spacing"]
reference_text = "Reference"
target_styles = ["BodyTight"]
exact_reference = true
[fidelity]
pagination = "may-change"
raster_tolerance = 0.3
ink_threshold = 180
dpi = 100
"""
)


def write(tmp_path: Path, text: str) -> Path:
    """Write a plan fixture.

    Returns
    -------
    Path
        The persisted review file.

    """
    path = tmp_path / "review.plan.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_full_plan_compiles_in_canonical_order(tmp_path: Path) -> None:
    plan = load_plan(write(tmp_path, FULL))
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    operations = compile_operations(document, plan)
    assert [item.name for item in operations] == [
        "set_odf_version",
        "set_metadata",
        "linkify_addresses",
        "remove_empty_spacers",
        "set_graphic_alternatives",
        "mark_table_headers",
        "normalize_spacing",
    ]
    assert operations[1].as_dict() == {
        "operation": "set_metadata",
        "title": "Decision",
        "description": "Decision letter",
        "language": "en-GB",
    }
    assert plan.fidelity == FidelityPolicy("may-change", 0.3, 180, 100)


def test_header_only_plan_requests_nothing(tmp_path: Path) -> None:
    plan = load_plan(write(tmp_path, HEADER))
    assert plan.decisions == ()
    assert plan.fidelity == FidelityPolicy()


def test_false_switches_compile_no_operations(tmp_path: Path) -> None:
    plan = load_plan(
        write(
            tmp_path,
            HEADER
            + """
[decisions."text.linkify_addresses"]
enabled = false
[decisions."text.remove_spacers"]
enabled = false
""",
        )
    )
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    assert compile_operations(document, plan) == ()


@pytest.mark.parametrize(
    "content",
    [
        '[decisions."document.metadata"]\ntitel = "Typo"',
        '[decisions."document.metadata"]\nlanguage = 7',
        '[decisions."document.odf_version"]\nversion = "1.2"',
        '[decisions."text.linkify_addresses"]\nenabled = "false"',
        '[decisions."table.headers"]\n"content/table[1]" = true',
        '[decisions."table.headers"]\n"content/table[1]" = 0',
        '[decisions."table.headers"."content/table[1]"]\nrows = 1\nextra = 1',
        '[decisions."table.headers"."content/table[1]"]\nfingerprint = "0123456789abcdef"',
        '[decisions]\n"text.spacing" = 1',
        '[decisions."missing.kind"]',
        '[decisions."graphic.alternative"."content/frame[1]"]\ndescription = 7',
        '[decisions."graphic.alternative"."content/frame[1]"]\ndescripton = "Typo"',
        'document = "invalid"',
        "[unknown]",
        "[unrecognised_family]",
        "[remediation]",
        "[alt_text]",
        '[decisions."text.spacing"]\nreference_text = "x"',
        '[decisions."text.spacing"]\ntarget_styles = ["A"]',
        '[decisions."text.spacing"]\nreference_text = "x"\ntarget_styles = ["A"]\nexact = true',
        '[fidelity]\npagination = "never"',
        "[fidelity]\nraster_tolerance = -1",
        "[fidelity]\nink_threshold = 300",
        "[fidelity]\ndpi = 0",
        "not = valid = toml",
    ],
)
def test_invalid_plan_is_rejected(tmp_path: Path, content: str) -> None:
    with pytest.raises(PlanError):
        load_plan(write(tmp_path, HEADER + content))


def test_missing_plan_file_is_a_plan_error(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="Cannot read plan"):
        load_plan(tmp_path / "absent.toml")


def test_example_plan_is_valid(tmp_path: Path) -> None:
    guide = (Path(__file__).resolve().parents[1] / "docs/PLAN.md").read_text(encoding="utf-8")
    example = guide.split("```toml\n", 1)[1].split("\n```", 1)[0]
    plan = load_plan(write(tmp_path, example))
    assert plan.decisions[0].answer_as(DocumentMetadataAnswer).title == "Example report"


@pytest.mark.parametrize("tag", ["en-u", "en-a-foo-a-bar", "sl-rozaj-rozaj"])
def test_plan_rejects_malformed_language_syntax(tmp_path: Path, tag: str) -> None:
    path = write(tmp_path, HEADER + f'[decisions."document.metadata"]\nlanguage = "{tag}"\n')
    with pytest.raises(PlanError, match="Invalid language"):
        load_plan(path)
