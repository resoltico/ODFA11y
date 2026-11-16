# SPDX-License-Identifier: MPL-2.0
"""Family analyses compose observed review guidance and omit absent optional content."""

import pytest

from odfa11y import run
from odfa11y.audit import audit_odf
from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.plans import Plan
from odfa11y.status import Profile
from tests.fixtures.documents import KIND_SPECS, Variant, make_flat, make_package
from tests.fixtures.paths import TESTS


def test_database_run_keeps_object_privacy_and_source_boundary_guidance(tmp_path) -> None:
    body = KIND_SPECS["database"].body.replace(
        "</office:database>",
        '<db:queries><db:query db:name="Counts" db:command="SELECT 1" '
        'db:description="Invented observation count"/></db:queries></office:database>',
    )
    source = make_package(tmp_path, "database", Variant(body=body))
    assert validate(OdfDocument.open(source)).count == 0
    result = run(source, Plan.for_source(source), tmp_path / "bundle", profile=Profile.SOURCE)
    assert result.exit_status == 0
    assert {item.key for item in result.human_review} == {
        Topic.DATABASE_MEANING,
        Topic.PRIVACY_AND_EXECUTION,
        Topic.SOURCE_BOUNDARY,
    }
    review = (tmp_path / "bundle/REVIEW.md").read_text()
    assert "Whether object descriptions explain queries" in review
    assert "Review credentials, bindings, SQL and macros offline" in review


def test_database_without_objects_or_connections_omits_optional_topics(tmp_path) -> None:
    source = make_package(tmp_path, "database", Variant(body="<office:database/>"))
    topics = set(audit_odf(source).review_topics)
    assert Topic.SOURCE_BOUNDARY in topics
    assert not {Topic.DATABASE_MEANING, Topic.PRIVACY_AND_EXECUTION} & topics


@pytest.mark.parametrize(
    ("filename", "required"),
    [
        ("sum-formula.odf", {Topic.MATHEMATICS, Topic.LANGUAGE, Topic.EXPORT_BOUNDARY}),
        ("fruit-chart.odc", {Topic.CHART_MEANING, Topic.LABELS_AND_RANGES, Topic.SOURCE_ASSURANCE}),
        ("fruit-image.odi", {Topic.IMAGE_MEANING, Topic.SOURCE_BOUNDARY}),
        ("fruit-drawing.odg", {Topic.LAYERS_AND_ANNOTATIONS}),
    ],
)
def test_observed_native_content_establishes_its_review_boundary(filename, required) -> None:
    report = audit_odf(TESTS / "corpus/families" / filename)
    assert required <= set(report.review_topics)
    assert len(report.review_topics) == len(set(report.review_topics))


def test_drawing_without_layers_or_annotations_omits_that_topic(tmp_path) -> None:
    source = make_flat(tmp_path, "drawing")
    assert Topic.LAYERS_AND_ANNOTATIONS not in audit_odf(source).review_topics


@pytest.mark.parametrize("hidden", [False, True])
def test_spreadsheet_hidden_rows_establish_only_present_review_topics(tmp_path, hidden) -> None:
    source = make_flat(tmp_path, "spreadsheet")
    if hidden:
        document = OdfDocument.open(source)
        row = select_elements(document.tree(Part.CONTENT), "//table:table-row")[0]
        row.set(qn("table", "visibility"), "collapse")
        document.save(source)
    assert (Topic.HIDDEN_CONTENT in audit_odf(source).review_topics) is hidden
