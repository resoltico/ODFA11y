# SPDX-License-Identifier: MPL-2.0
"""Kinds own answer meaning; family registration and rules derive from that ownership."""

from copy import deepcopy
from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.decisions import DecisionScope
from odfa11y.errors import PlanError
from odfa11y.families.text.domains import HEADINGS
from odfa11y.odf import OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.plans.registry import registered_kinds
from odfa11y.rules import registry as rules
from odfa11y.targets import TargetPath
from tests.fixtures.paths import TESTS
from tests.fixtures.writer import make_minimal_odt


def test_every_targeted_kind_owns_a_domain_and_resolved_rules_are_registered_objects() -> None:
    for kind in registered_kinds().values():
        assert (kind.domain is not None) == (kind.scope is DecisionScope.TARGET)
        assert all(rules.RULES[rule.id] is rule for rule in kind.resolves)


def test_chart_description_finding_raises_its_common_metadata_question_in_the_same_call() -> None:
    report = audit_odf(TESTS / "corpus/families/fruit-chart.odc")
    assert any(finding.rule is rules.CHART004 for finding in report.findings)
    (question,) = [
        question for question in report.decisions if question.kind.id == "document.metadata"
    ]
    assert rules.CHART004.id in question.rule_ids


def test_target_resolution_refuses_a_missing_or_ambiguous_canonical_identity(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    document = OdfDocument.open(source)
    heading = next(document.tree(Part.CONTENT).iter(xml_names.TEXT_H))
    heading.set(xml_names.XML_ID, "same")
    parent = heading.getparent()
    assert parent is not None
    parent.append(deepcopy(heading))
    for path in ("content/heading[id=same]", "content/heading[99]"):
        with pytest.raises(PlanError, match="exactly one"):
            HEADINGS.resolve(document, TargetPath(path))
