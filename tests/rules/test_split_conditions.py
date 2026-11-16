# SPDX-License-Identifier: MPL-2.0
"Each split finding has a triggering fixture and a repaired negative control."

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.audit.package import _part_of, audit_structure, audit_versions
from odfa11y.families.text.lists import audit_lists
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.odf.names import XML_ID
from odfa11y.report import Report, ReportKind
from odfa11y.rules import registry as rules
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.paths import TESTS

ITEM = "<text:list-item><text:p>Item</text:p></text:list-item>"
LIST = f'<text:list xml:id="a" text:style-name="Numbers">{ITEM}</text:list>'
NOTE = (
    '<text:note text:id="n" text:note-class="footnote"><text:note-citation>1'
    "</text:note-citation><text:note-body><text:p>Body</text:p></text:note-body></text:note>"
)
REGION = (
    '<text:tracked-changes><text:changed-region xml:id="r"><text:deletion/>'
    "</text:changed-region></text:tracked-changes>"
)
MARK = '<text:p><text:change text:change-id="r"/></text:p>'


@pytest.mark.parametrize(
    ("rule", "broken", "repaired"),
    [
        (
            rules.HEADING002.id,
            '<text:h text:outline-level="2">Title</text:h>',
            '<text:h text:outline-level="1">Title</text:h>',
        ),
        (
            rules.HEADING003.id,
            (
                '<text:h text:outline-level="1">Title</text:h>'
                '<text:h text:outline-level="3">Sub</text:h>'
            ),
            (
                '<text:h text:outline-level="1">Title</text:h>'
                '<text:h text:outline-level="2">Sub</text:h>'
            ),
        ),
        (rules.LIST002.id, "<text:list><text:p>Not an item</text:p></text:list>", LIST),
        (
            rules.LIST003.id,
            f"<text:list>{LIST}</text:list>",
            f"<text:list><text:list-item>{LIST}</text:list-item></text:list>",
        ),
        (
            rules.LIST004.id,
            f'<text:list text:continue-numbering="yes">{ITEM}</text:list>',
            LIST,
        ),
        (
            rules.LIST005.id,
            f'<text:list xml:id="a" text:continue-list="a">{ITEM}</text:list>',
            LIST,
        ),
        (
            rules.LIST006.id,
            f'<text:list text:continue-list="missing">{ITEM}</text:list>',
            LIST,
        ),
        (
            rules.LIST007.id,
            (
                "<table:table><table:table-row><table:table-cell>"
                f"{LIST}</table:table-cell><table:table-cell>"
                f'<text:list text:continue-list="a">{ITEM}</text:list>'
                "</table:table-cell></table:table-row></table:table>"
            ),
            LIST + f'<text:list text:continue-list="a">{ITEM}</text:list>',
        ),
        (
            rules.LIST008.id,
            f'<text:list text:continue-numbering="true">{ITEM}</text:list>',
            LIST
            + (
                '<text:list text:style-name="Numbers" text:continue-numbering="true">'
                f"{ITEM}</text:list>"
            ),
        ),
        (
            rules.NOTE002.id,
            f'<text:p>{NOTE}<text:note-ref text:ref-name="n" text:note-class="endnote"/></text:p>',
            f'<text:p>{NOTE}<text:note-ref text:ref-name="n" text:note-class="footnote"/></text:p>',
        ),
        (
            rules.NOTE003.id,
            '<text:p><text:note text:id="n" text:note-class="footnote"/></text:p>',
            f"<text:p>{NOTE}</text:p>",
        ),
        (rules.NOTE004.id, f"<text:p>{NOTE}{NOTE}</text:p>", f"<text:p>{NOTE}</text:p>"),
        (
            rules.REVISION001.id,
            REGION.replace('xml:id="r"', 'xml:id="r" text:id="other"') + MARK,
            REGION + MARK,
        ),
        (rules.REVISION002.id, REGION + MARK + MARK, REGION + MARK),
        (rules.REVISION003.id, MARK, REGION + MARK),
        (rules.REVISION004.id, REGION, REGION + MARK),
        (
            rules.REVISION005.id,
            REGION + f'<text:section text:name="Hidden" text:display="none">{MARK}</text:section>',
            REGION + MARK,
        ),
    ],
)
def test_text_conditions(tmp_path: Path, rule: str, broken: str, repaired: str) -> None:
    for body, expected in ((repaired, False), (broken, True)):
        source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
        assert (rule in {finding.rule_id for finding in audit_odf(source).findings}) is expected


@pytest.mark.parametrize(
    ("rule", "broken", "repaired"),
    [
        (
            rules.DATABASE001.id,
            "<office:database/><office:database/>",
            "<office:database/>",
        ),
        (
            rules.DATABASE002.id,
            "<office:database/>",
            (
                "<office:database>"
                '<db:connection-resource xlink:href="sdbc:embedded:hsqldb"/>'
                "</office:database>"
            ),
        ),
        (
            rules.DATABASE003.id,
            (
                "<office:database>"
                '<db:connection-resource xlink:href="sdbc:embedded:hsqldb"/>'
                "</office:database>"
            ),
            (
                "<office:database>"
                '<db:connection-resource xlink:href="sdbc:external"/>'
                "</office:database>"
            ),
        ),
        (
            rules.DATABASE005.id,
            '<office:database><db:login db:user-name="user"/></office:database>',
            "<office:database><db:login/></office:database>",
        ),
        (
            rules.DATABASE006.id,
            (
                "<office:database>"
                '<db:connection-resource xlink:href="sdbc:external?user=private"/>'
                "</office:database>"
            ),
            (
                "<office:database>"
                '<db:connection-resource xlink:href="sdbc:external"/>'
                "</office:database>"
            ),
        ),
        (
            rules.DATABASE007.id,
            (
                "<office:database>"
                '<db:data-source-setting db:data-source-setting-name="password" '
                'db:data-source-setting-type="string">'
                "<db:data-source-setting-value>"
                "secret</db:data-source-setting-value></db:data-source-setting>"
                "</office:database>"
            ),
            "<office:database/>",
        ),
        (
            rules.DATABASE008.id,
            ('<office:database><db:query db:name="Q"/><db:query db:name="Q"/></office:database>'),
            '<office:database><db:query db:name="Q"/></office:database>',
        ),
        (
            rules.DATABASE009.id,
            '<office:database><db:query db:name="Q"/></office:database>',
            (
                "<office:database>"
                '<db:query db:name="Q" db:description="Description"/>'
                "</office:database>"
            ),
        ),
        (
            rules.DATABASE011.id,
            '<office:database><db:query db:name="Q"/></office:database>',
            "<office:database/>",
        ),
        (
            rules.DATABASE012.id,
            '<office:database><db:component db:name="Form"/></office:database>',
            "<office:database/>",
        ),
        (
            rules.PAGE001.id,
            "<office:presentation/>",
            '<office:presentation><draw:page draw:name="Page"/></office:presentation>',
        ),
        (
            rules.PAGE002.id,
            "<office:presentation><draw:page/></office:presentation>",
            '<office:presentation><draw:page draw:name="Page"/></office:presentation>',
        ),
        (
            rules.IMAGE003.id,
            "<office:image/>",
            (
                '<office:image><draw:frame draw:name="Picture"><draw:image/>'
                "</draw:frame></office:image>"
            ),
        ),
        (
            rules.IMAGE004.id,
            '<office:image><draw:frame draw:name="Picture"/></office:image>',
            (
                '<office:image><draw:frame draw:name="Picture"><draw:image/>'
                "</draw:frame></office:image>"
            ),
        ),
    ],
)
def test_family_conditions(tmp_path: Path, rule: str, broken: str, repaired: str) -> None:
    kind = (
        "database"
        if rule.startswith("DATABASE")
        else "presentation"
        if rule.startswith("PAGE")
        else "image"
    )
    for body, expected in ((repaired, False), (broken, True)):
        source = make_flat(tmp_path, kind, Variant(body=body))
        assert (rule in {finding.rule_id for finding in audit_odf(source).findings}) is expected


def _chart_change(document: OdfDocument, condition: str) -> None:
    chart = select_elements(document.tree(Part.CONTENT), "//chart:chart")[0]
    plot = select_elements(chart, "./chart:plot-area")[0]
    series = select_elements(plot, "./chart:series")[0]
    match condition:
        case "body":
            parent = chart.getparent()
            assert parent is not None
            parent.remove(chart)
        case "series":
            plot.remove(series)
        case "provider":
            chart.set(qn("xlink", "href"), "https://invalid.example/data")
        case "cache":
            series.set(qn("chart", "values-cell-range-address"), "absent.$B$2:.$B$3")
        case "labels":
            for node in select_elements(
                chart,
                (".//table:table-cell[@office:value-type='string']/text:p | .//chart:title/text:p"),
            ):
                node.text = ""
        case "dimensions":
            series.set(qn("chart", "values-cell-range-address"), "local-table.$A$2:.$B$3")
        case "length":
            select_elements(chart, ".//chart:categories")[0].set(
                qn("table", "cell-range-address"), "local-table.$A$2"
            )
        case "numeric":
            series.set(qn("chart", "values-cell-range-address"), "local-table.$B$1:.$B$3")


@pytest.mark.parametrize(
    ("rule", "condition"),
    [
        (rules.CHART001.id, "body"),
        (rules.CHART002.id, "series"),
        (rules.CHART006.id, "provider"),
        (rules.CHART007.id, "cache"),
        (rules.CHART008.id, "labels"),
        (rules.CHART009.id, "dimensions"),
        (rules.CHART010.id, "length"),
        (rules.CHART011.id, "numeric"),
    ],
)
def test_chart_conditions(tmp_path: Path, rule: str, condition: str) -> None:
    source = TESTS / "family_corpus/fruit-chart.odc"
    assert rule not in {finding.rule_id for finding in audit_odf(source).findings}
    document = OdfDocument.open(source)
    _chart_change(document, condition)
    assert rule in {
        finding.rule_id for finding in audit_odf(document.save(tmp_path / "broken.odc")).findings
    }


@pytest.mark.parametrize(
    ("rule", "member", "xpath"),
    [
        (rules.ODF003.id, Part.MANIFEST, "."),
        (rules.ODF004.id, Part.MANIFEST, "./manifest:file-entry"),
    ],
)
def test_version_conditions(tmp_path: Path, rule: str, member: Part, xpath: str) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    audit_versions(document, report)
    assert rule not in {finding.rule_id for finding in report.findings}
    select_elements(document.tree(member), xpath)[0].set(qn("manifest", "version"), "1.3")
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    audit_versions(document, report)
    assert rule in {finding.rule_id for finding in report.findings}


@pytest.mark.parametrize("rule", [rules.MATH001.id, rules.MATH002.id])
def test_formula_conditions(tmp_path: Path, rule: str) -> None:
    source = TESTS / "family_corpus/sum-formula.odf"
    assert rule not in {finding.rule_id for finding in audit_odf(source).findings}
    document = OdfDocument.open(source)
    root = document.tree(Part.CONTENT).getroot()
    if rule == rules.MATH001.id:
        root.tag = qn("office", "document-content")
    else:
        for child in list(root):
            root.remove(child)
    assert rule in {
        finding.rule_id for finding in audit_odf(document.save(tmp_path / "broken.odf")).findings
    }


def test_unknown_schema_member_has_no_invented_part(tmp_path: Path) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    assert _part_of(document, "Object/content.xml") is None


@pytest.mark.parametrize("extension", [".fodt", ".xml", ".foo", ".fods"])
def test_flat_extension_matches_kind(tmp_path: Path, extension: str) -> None:
    report = audit_odf(make_flat(tmp_path, "text", Variant(extension=extension)))
    assert (rules.ODF008.id in {finding.rule_id for finding in report.findings}) is (
        extension not in {".fodt", ".xml"}
    )


def test_duplicate_list_identity_is_measured_in_memory(tmp_path: Path) -> None:
    document = OdfDocument.open(
        make_flat(tmp_path, "text", Variant(body=f"<office:text>{LIST}</office:text>"))
    )
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    audit_lists(document, report)
    assert rules.LIST001.id not in {finding.rule_id for finding in report.findings}
    original = select_elements(document.tree(Part.CONTENT), "//text:list")[0]
    parent = original.getparent()
    assert parent is not None
    duplicate = etree.SubElement(parent, qn("text", "p"))
    duplicate.set(XML_ID, "a")
    audit_lists(document, report)
    assert rules.LIST001.id in {finding.rule_id for finding in report.findings}


@pytest.mark.parametrize("rule", [rules.PKG002.id, rules.PKG003.id, rules.PKG004.id])
def test_media_type_conditions(tmp_path: Path, rule: str) -> None:
    source = (make_flat if rule == rules.PKG002.id else make_package)(tmp_path, "text")
    document = OdfDocument.open(source)
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    audit_structure(document, report)
    assert rule not in {finding.rule_id for finding in report.findings}
    if rule == rules.PKG002.id:
        document.tree(Part.CONTENT).getroot().attrib.pop(qn("office", "mimetype"))
        document = OdfDocument.open(document.save(tmp_path / "missing.fodt"))
    elif rule == rules.PKG003.id:
        document = OdfDocument.open(make_package(tmp_path, "text", Variant(mimetype=False)))
    else:
        document.storage.write_member("mimetype", document.storage.read("mimetype") + b" ")
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    audit_structure(document, report)
    assert rule in {finding.rule_id for finding in report.findings}
