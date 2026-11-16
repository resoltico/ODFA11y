# SPDX-License-Identifier: AGPL-3.0-only
"""Review values remain literal data under an independent CommonMark renderer."""

from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.concepts.review import ReviewTopic
from odfa11y.errors import DocumentRefusal
from odfa11y.evidence.redact import Redactor
from odfa11y.families.spec import ReviewItem
from odfa11y.progress import Stage
from odfa11y.remediate.result import RemediationResult, SchemaCheck, UnansweredReview
from odfa11y.report import Report, ReportKind
from odfa11y.rules import registry as rules
from odfa11y.run.record import StageResult
from odfa11y.run.review import render_review
from odfa11y.status import Passed, Profile, Refused
from odfa11y.targets import TargetPath
from tests.fixtures.records import record


class RenderedReview(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []
        self.strong_text = []
        self.in_strong = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "strong":
            self.in_strong = True

    def handle_endtag(self, tag):
        if tag == "strong":
            self.in_strong = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_strong:
            self.strong_text.append(data)


@pytest.mark.parametrize("injected", [False, True])
def test_all_review_values_are_literal_after_redaction(injected) -> None:
    value = (
        "`code` <img src=http://127.0.0.1:9/canary.png> **bold** "
        "[link](https://example.invalid/) &lt;value&gt;\n# OWNED\n"
        "/private/review-canary/secret.txt"
        if injected
        else "Ordinary review value"
    )
    report = Report[object](
        kind=ReportKind.ODF, subject="source.odt", facts=(DocumentMetadata(title=value),)
    )
    report.raise_(rules.META001, value)
    target = TargetPath.named("content", "frame", value)
    remediation = RemediationResult(
        _source=Path("source.odt"),
        _destination=None,
        outcomes=(),
        schema=SchemaCheck("1.4", 0, 0),
        unanswered=(UnansweredReview(value, target, False),),
    )
    result = replace(
        record(),
        source_name=value,
        profile=Profile.SOURCE,
        human_review=(ReviewItem(ReviewTopic.READING_ORDER, value),),
        stages=(
            StageResult(Stage.AUDIT_SOURCE, Passed(report)),
            StageResult(Stage.EXPORT_SOURCE, Refused(DocumentRefusal(value))),
            StageResult(Stage.REMEDIATE, Passed(), remediation),
        ),
    )
    redactor = Redactor.for_locations({"private": Path("/private/review-canary")})
    markdown = render_review(result, redactor=redactor)
    parsed = RenderedReview()
    parsed.feed(MarkdownIt("commonmark").render(markdown))
    assert "img" not in parsed.tags
    assert "a" not in parsed.tags
    assert parsed.tags.count("h1") == 1
    assert parsed.tags.count("h2") == 4
    visible = "".join(parsed.text)
    if injected:
        assert "<img src=http://127.0.0.1:9/canary.png>" in visible
        assert "[link](https://example.invalid/)" in visible
        assert "**bold**" in visible
        assert "bold" not in "".join(parsed.strong_text)
        assert "&lt;value&gt;" in visible
        assert "/private/review-canary" not in markdown
        assert "/private/review-canary" not in visible
    else:
        assert value in visible
    # Presentation escaping must not rewrite the producer's machine values.
    assert result.source_name == value
    facts = report.as_dict()["facts"]
    assert isinstance(facts, list)
    metadata = facts[0]
    assert isinstance(metadata, dict)
    assert metadata["title"] == value
