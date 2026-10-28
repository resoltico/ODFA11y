# SPDX-License-Identifier: MPL-2.0
"""Read-only language inspection reports unresolved declarations without guessing a remedy."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf, prepare_plan

from .documents import Variant, make_flat
from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "problem", ["default-style", "text-properties", "tag", "tag-no-metadata", "metadata"]
)
def test_audit_reports_unresolved_language_without_configuration_guess(
    tmp_path: Path, problem: str
) -> None:
    source = make_minimal_odt(tmp_path / "original.odt")
    document = OdfDocument.open(source)
    default = document.tree(Part.STYLES).find("office:styles/style:default-style", NS)
    assert default is not None
    props = default.find("style:text-properties", NS)
    assert props is not None
    if problem in {"default-style", "text-properties"}:
        node = default if problem == "default-style" else props
        parent = node.getparent()
        assert parent is not None
        parent.append(deepcopy(node))
    elif problem in {"tag", "tag-no-metadata"}:
        props.set(qn("style", "rfc-language-tag"), "en-u")
        if problem == "tag-no-metadata":
            metadata = document.tree(Part.META).find("office:meta", NS)
            assert metadata is not None
            language = metadata.find("dc:language", NS)
            assert language is not None
            metadata.remove(language)
    else:
        language = document.tree(Part.META).find("office:meta/dc:language", NS)
        assert language is not None
        language.text = "en-u"
    destination = document.save(tmp_path / "unresolved.odt")
    original = destination.read_bytes()
    report, template = prepare_plan(destination)
    findings = [finding for finding in report.findings if finding.rule_id == "META004"]
    assert len(findings) == 1
    assert not any(findings[0].rule_id in d.rule_ids for d in report.decisions)
    assert findings[0].details
    assert "META002" not in {finding.rule_id for finding in report.findings}
    assert template is not None
    assert "# language =" not in template
    assert destination.read_bytes() == original


def test_foreign_metadata_never_becomes_document_metadata(tmp_path: Path) -> None:
    body = (
        '<office:text><text:p>Visible words</text:p><foreign:payload xmlns:foreign="urn:foreign">'
        "<office:meta><dc:title>Foreign title</dc:title>"
        "<dc:description>Foreign description</dc:description>"
        "<dc:language>es-419</dc:language></office:meta></foreign:payload></office:text>"
    )
    source = make_flat(tmp_path, "text", Variant(body=body))
    tree = etree.parse(source)
    meta = tree.find("office:meta", NS)
    assert meta is not None
    tree.getroot().remove(meta)
    tree.write(source, encoding="utf-8", xml_declaration=True)
    report = audit_odf(source)
    assert {"META001", "META002"} <= {finding.rule_id for finding in report.findings}
    assert (
        not {FactKeys.DOCUMENT_TITLE, FactKeys.DOCUMENT_DESCRIPTION, FactKeys.DOCUMENT_LANGUAGE}
        & report.facts.keys()
    )
