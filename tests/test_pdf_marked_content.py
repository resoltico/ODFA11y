# SPDX-License-Identifier: MPL-2.0
"""Marked-content reconciliation, verified against independently built content streams."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

import pytest
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf import audit_pdfua
from odfa11y.pdf import marked_content as marked
from odfa11y.pdf.content_scan import scan_content

from .pdf_fixtures import dictionary, marked_text, set_page_content, tagged_writer, text_pdf

if TYPE_CHECKING:
    from pathlib import Path

    from pypdf import PdfWriter
    from pypdf.generic import IndirectObject

    from odfa11y.report import Finding, Report

CONTENT_RULES = {"PDF020", "PDF021", "PDF022", "PDF023"}
TEXT = "BT /F1 12 Tf 10 50 Td (x) Tj ET"


def audit(tmp_path: Path, writer: PdfWriter) -> Report:
    """Write a synthetic PDF and audit it.

    Returns
    -------
    Report
        The audit of the written file.

    """
    path = tmp_path / "synthetic.pdf"
    writer.write(path)
    return audit_pdfua(path)


def content_findings(report: Report) -> dict[str, Finding]:
    """Index the marked-content findings by rule.

    Returns
    -------
    dict[str, Finding]
        The finding of each content rule that fired.

    """
    return {f.rule_id: f for f in report.findings if f.rule_id in CONTENT_RULES}


def leaves(writer: PdfWriter) -> list[IndirectObject]:
    """List the structure elements of a ``tagged_writer`` PDF that have no element kids.

    Returns
    -------
    list[IndirectObject]
        The leaf elements in tree order.

    """
    found: list[IndirectObject] = []
    tree = dictionary(cast("IndirectObject", writer.root_object["/StructTreeRoot"]))
    pending = list(reversed(cast("ArrayObject", tree["/K"])))
    while pending:
        reference = pending.pop()
        kids = dictionary(reference)["/K"]
        if isinstance(kids, ArrayObject):
            pending.extend(reversed(kids))
        else:
            found.append(reference)
    return found


def set_content(writer: PdfWriter, operators: str) -> None:
    set_page_content(writer, writer.pages[0], operators)


def test_content_that_every_element_and_sequence_agrees_on_has_no_findings(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", ("L", [("LI", ["P"])]), "P"]))
    assert not content_findings(report)
    assert report.metadata["marked_content_ids"] == 3


def test_marked_content_no_structure_element_refers_to_is_an_error(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    set_content(writer, f"{marked_text(0)}\n{marked_text(7)}\n{marked_text(3)}")
    finding = content_findings(audit(tmp_path, writer))["PDF020"]
    assert finding.severity.value == "error"
    assert finding.details["pages"] == [{"page": 1, "count": 2, "mcids": [3, 7]}]


def test_a_reference_to_marked_content_the_page_lacks_is_a_warning(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", "P"])
    set_content(writer, marked_text(0))
    findings = content_findings(audit(tmp_path, writer))
    assert set(findings) == {"PDF021"}
    assert findings["PDF021"].severity.value == "warning"
    assert findings["PDF021"].details["references"] == [{"page": 1, "mcid": 1}]


def test_a_reference_resolved_through_another_page_is_not_content_of_this_page(
    tmp_path: Path,
) -> None:
    writer = tagged_writer(["H1", "P"])
    other = writer.add_blank_page(width=100, height=100)
    dictionary(leaves(writer)[1])[NameObject("/Pg")] = other.indirect_reference
    findings = content_findings(audit(tmp_path, writer))
    assert set(findings) == {"PDF020", "PDF021"}
    assert findings["PDF021"].details["references"] == [{"page": 2, "mcid": 1}]


def test_marked_content_referred_to_twice_is_a_warning(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", "P"])
    dictionary(leaves(writer)[1])[NameObject("/K")] = NumberObject(0)
    findings = content_findings(audit(tmp_path, writer))
    assert set(findings) == {"PDF020", "PDF022"}
    assert findings["PDF022"].severity.value == "warning"
    assert findings["PDF022"].details["mcids"] == [{"page": 1, "mcid": 0, "references": 2}]


def test_a_marked_content_reference_dictionary_counts_like_an_integer(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    page = writer.pages[0].indirect_reference
    reference = DictionaryObject({
        NameObject("/Type"): NameObject("/MCR"),
        NameObject("/MCID"): NumberObject(0),
        NameObject("/Pg"): page,
    })
    dictionary(leaves(writer)[0])[NameObject("/K")] = ArrayObject([reference])
    assert not content_findings(audit(tmp_path, writer))
    reference[NameObject("/MCID")] = NumberObject(4)
    assert set(content_findings(audit(tmp_path, writer))) == {"PDF020", "PDF021"}


def test_a_reference_into_a_form_xobject_is_not_judged_against_the_page(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    reference = DictionaryObject({
        NameObject("/Type"): NameObject("/MCR"),
        NameObject("/MCID"): NumberObject(9),
        NameObject("/Pg"): writer.pages[0].indirect_reference,
        NameObject("/Stm"): writer.pages[0].indirect_reference,
    })
    dictionary(leaves(writer)[0])[NameObject("/K")] = ArrayObject([NumberObject(0), reference])
    assert not content_findings(audit(tmp_path, writer))


@pytest.mark.parametrize(
    "operators",
    [
        TEXT,
        f"/Span BMC {TEXT} EMC",
        f"/Span <</ActualText (x)>> BDC {TEXT} EMC",
        f"{marked_text(0)}\n{TEXT}",
        f"{marked_text(0)}\n/Artifact BMC EMC {TEXT}",
    ],
)
def test_text_outside_tagged_content_and_artifacts_is_an_error(
    tmp_path: Path, operators: str
) -> None:
    writer = tagged_writer(["H1"])
    set_content(writer, operators)
    finding = content_findings(audit(tmp_path, writer))["PDF023"]
    assert finding.severity.value == "error"
    assert finding.details["pages"] == [{"page": 1, "text_operations": 1}]


@pytest.mark.parametrize(
    "operators",
    [
        f"/Artifact BMC {TEXT} EMC",
        f"/Artifact <</Type /Pagination>> BDC {TEXT} EMC",
        f"/P <</MCID 0>> BDC /Span BMC {TEXT} EMC (kept) ' EMC",
        f"/P /MC0 BDC {TEXT} EMC",
        f"/P <</MCID 0>> BDC /Artifact BMC {TEXT} EMC {TEXT} EMC",
    ],
)
def test_tagged_and_artifact_text_is_accepted(tmp_path: Path, operators: str) -> None:
    writer = tagged_writer(["H1"])
    set_content(writer, operators)
    assert "PDF023" not in content_findings(audit(tmp_path, writer))


def test_a_properties_resource_supplies_the_mcid_of_a_named_property_list(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    set_content(writer, f"/P /MC0 BDC {TEXT} EMC")
    assert not content_findings(audit(tmp_path, writer))


def test_a_named_property_list_without_an_mcid_does_not_tag_content(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    set_content(writer, f"/P /MC0 BDC {TEXT} EMC")
    resources = cast("DictionaryObject", writer.pages[0]["/Resources"])
    cast("DictionaryObject", resources["/Properties"])[NameObject("/MC0")] = DictionaryObject()
    assert {"PDF021", "PDF023"} <= set(content_findings(audit(tmp_path, writer)))


def test_a_pdf_without_a_structure_tree_is_left_to_the_tagging_rules(tmp_path: Path) -> None:
    report = audit_pdfua(text_pdf(tmp_path / "untagged.pdf", [["x"]]))
    assert "PDF004" in {f.rule_id for f in report.findings}
    assert not content_findings(report)


def test_every_page_is_reconciled_with_its_own_content(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", "P"])
    second = writer.add_blank_page(width=100, height=100)
    set_page_content(writer, second, marked_text(0))
    dictionary(leaves(writer)[1])[NameObject("/Pg")] = second.indirect_reference
    dictionary(leaves(writer)[1])[NameObject("/K")] = NumberObject(0)
    set_content(writer, marked_text(0))
    assert not content_findings(audit(tmp_path, writer))


@pytest.mark.parametrize(
    ("data", "mcids", "unmarked"),
    [
        (b"/P <</MCID 2>> BDC (EMC ) Tj EMC", {2}, 0),
        (b"/P <</MC#49D +2>> BDC (x) Tj EMC", {2}, 0),
        (b"/Arti#66act BMC (x) Tj EMC", set(), 0),
        (b"/P <</MCID 2>> BDC (a \\) EMC) Tj EMC (b) Tj", {2}, 1),
        (b"/P <</MCID 2>> BDC (nested (EMC) ) Tj EMC (b) Tj", {2}, 1),
        (b"/P <</MCID 4>> BDC <454d43> Tj % EMC (\n EMC (x) Tj", {4}, 1),
        (b"BI /W 1 /H 1 /CS /G /BPC 8 ID \x00 EI /P <</MCID 1>> BDC EMC", {1}, 0),
        (b"BI /W 13 /H 1 /CS /G /BPC 8 ID  EI (fake) Tj  EI", set(), 0),
        (b"/P <</MCID 3 /Lang (en)>> BDC [(a) -20 (b)] TJ EMC", {3}, 0),
        (b"/P <</A <</MCID 8>> /MCID 5>> BDC EMC", {5}, 0),
        (b"/P <</MCID 99999999999999999999>> BDC EMC", {99999999999999999999}, 0),
        (b"EMC EMC (x) Tj", set(), 1),
        (b"(never closed Tj", set(), 0),
        (b"/P <</MCID x>> BDC (x) Tj EMC", set(), 1),
        (b"/P BDC (x) Tj EMC", set(), 1),
    ],
)
def test_content_scanning_follows_pdf_syntax(data: bytes, mcids: set[int], unmarked: int) -> None:
    scan = scan_content(data, lambda _name: None)
    assert (scan.mcids, scan.unmarked_text_operations) == (mcids, unmarked)


def test_hostile_content_scanning_keeps_results_and_meets_the_time_budget() -> None:
    hostile = [
        (b"/P <</MCID 1>> BDC " * 200_000, {1}),
        (b"(" * 2_000_000, set()),
        (b"<<" * 1_000_000 + b">>", set()),
        (b"/A " * 1_000_000, set()),
    ]
    started = time.perf_counter()
    for data, expected in hostile:
        scan = scan_content(data, lambda _name: None)
        assert (scan.mcids, scan.unmarked_text_operations) == (expected, 0)
    with pytest.raises(ToolFailedError, match="Inline image has no data delimiter"):
        scan_content(b"BI " * 500_000, lambda _name: None)
    assert time.perf_counter() - started < 10


def test_page_content_above_the_size_limit_is_reported_as_uninspectable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = tagged_writer(["H1"])
    path = tmp_path / "large.pdf"
    writer.write(path)
    monkeypatch.setattr(marked, "MAX_CONTENT_BYTES", 10)
    report = audit_pdfua(path)
    assert [f.rule_id for f in report.findings] == ["PDF000"]
    assert "larger than the 10-byte limit" in report.findings[0].message


def test_the_content_limit_covers_all_pages_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = tagged_writer(["H1"])
    second = writer.add_blank_page(width=100, height=100)
    set_page_content(writer, second, marked_text(0))
    page_bytes = len(marked_text(0))
    monkeypatch.setattr(marked, "MAX_CONTENT_BYTES", 2 * page_bytes - 1)
    report = audit(tmp_path, writer)
    assert [f.rule_id for f in report.findings] == ["PDF000"]
    monkeypatch.setattr(marked, "MAX_CONTENT_BYTES", 2 * page_bytes + 1)
    assert "PDF000" not in {f.rule_id for f in audit(tmp_path, writer).findings}


@pytest.mark.parametrize("filter_name", [b"F", b"Filter", b"Fi#6cter"])
def test_a_filtered_inline_image_is_refused_instead_of_guessing_its_end(
    filter_name: bytes,
) -> None:
    with pytest.raises(ToolFailedError, match="Filtered inline images"):
        scan_content(
            b"BI /W 1 /H 1 /CS /G /BPC 8 /" + filter_name + b" /Fl ID x EI",
            lambda _name: None,
        )
