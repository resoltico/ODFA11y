# SPDX-License-Identifier: MPL-2.0
"""Verify parsed PDF diagnostics with independent synthetic PDF objects."""

lazy from pathlib import Path

import pytest
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)
lazy from pypdf import PdfWriter

from odfa11y.pdf import audit_pdfua
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.pdf.structure.checks import PdfStructureMeasurements
from odfa11y.pdf.structure.links import PdfLinkMeasurements
from odfa11y.rules import registry as rules
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.pdf import (
    annotation_references,
    dictionary,
    link_elements,
    map_link,
    tagged_writer,
)
lazy from odfa11y.report import Report


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


def ids(report: Report) -> set[str]:
    """Collect rule identifiers.

    Returns
    -------
    set[str]
        The rule identifiers present.

    """
    return {finding.rule_id for finding in report.findings}


def test_valid_markers_and_indirect_preferences_are_detected(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer())
    assert report.error_count == 0, [f.as_dict() for f in report.findings]
    assert report.warning_count == 0
    assert measured(measurement(report, PdfMeasurements).ua_part) == 1
    assert measured(measurement(report, PdfStructureMeasurements).structure_tags) == {"H1": 1}
    assert measured(measurement(report, PdfMeasurements).text_character_count) > 0


@pytest.mark.parametrize(
    "mapping", [{"Illustration": "Figure"}, {"Illustration": "Picture", "Picture": "Figure"}]
)
def test_custom_figure_roles_require_alternative_text(
    tmp_path: Path, mapping: dict[str, str]
) -> None:
    report = audit(tmp_path, tagged_writer(["Illustration"], role_map=mapping))
    assert rules.PDF008.id in ids(report)
    assert rules.PDF012.id not in ids(report)


def test_figures_with_alternative_text_pass(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", "Figure"], figure_alt="A chart"))
    assert rules.PDF008.id not in ids(report)


@pytest.mark.parametrize("mapping", [None, {"Custom": "Other", "Other": "Custom"}])
def test_unmapped_and_cyclic_roles_are_rejected(
    tmp_path: Path, mapping: dict[str, str] | None
) -> None:
    assert rules.PDF012.id in ids(audit(tmp_path, tagged_writer(["Custom"], role_map=mapping)))


def test_false_marked_flag_is_rejected(tmp_path: Path) -> None:
    writer = tagged_writer()
    mark_info = writer.root_object["/MarkInfo"]
    assert isinstance(mark_info, DictionaryObject)
    mark_info[NameObject("/Marked")] = BooleanObject(value=False)
    assert rules.PDF004.id in ids(audit(tmp_path, writer))


def test_invalid_pdf_returns_error_report(tmp_path: Path) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a PDF")
    assert ids(audit_pdfua(path)) == {rules.PDF001.id}


def test_cyclic_structure_arrays_do_not_repeat_traversal(tmp_path: Path) -> None:
    writer = tagged_writer()
    structure = writer.root_object["/StructTreeRoot"]
    assert isinstance(structure, DictionaryObject)
    children = structure["/K"]
    assert isinstance(children, ArrayObject)
    children.append(writer._add_object(children))
    assert measured(
        measurement(audit(tmp_path, writer), PdfStructureMeasurements).structure_tags
    ) == {"H1": 1}


def test_skipped_heading_levels_are_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", "H3", "H2"]))
    finding = next(f for f in report.findings if f.rule_id == rules.PDF013.id)
    assert finding.details["skips"] == ["H1 to H3"]
    assert rules.PDF013.id not in ids(audit(tmp_path, tagged_writer(["H1", "H2", "H3", "H2"])))
    first = next(
        f
        for f in audit(tmp_path, tagged_writer(["H2", "H3"])).findings
        if f.rule_id == rules.PDF013.id
    )
    assert first.details["skips"] == ["start to H2"]


def test_well_formed_lists_and_tables_pass(tmp_path: Path) -> None:
    structure = [
        "H1",
        ("L", [("LI", ["Lbl", "LBody"]), ("LI", ["Lbl", ("LBody", [("L", [("LI", ["LBody"])])])])]),
        ("Table", [("TR", ["TH", "TH"]), ("TR", ["TD", "TD"]), ("TR", ["TD", "TD"])]),
        ("Table", [("THead", [("TR", ["TH"])]), ("TBody", [("TR", ["TD"])])]),
    ]
    report = audit(tmp_path, tagged_writer(structure))
    assert not ids(report) & {
        rules.PDF014.id,
        rules.PDF015.id,
        rules.PDF016.id,
    }, [f.as_dict() for f in report.findings]


def test_malformed_lists_are_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", ("L", ["P", ("LI", ["P"])])]))
    finding = next(f for f in report.findings if f.rule_id == rules.PDF014.id)
    assert finding.details["problems"] == ["L contains P", "LI contains P"]


def test_malformed_tables_are_reported(tmp_path: Path) -> None:
    structure = ["H1", ("Table", [("TH", []), ("TR", [("P", [])])])]
    finding = next(
        f
        for f in audit(tmp_path, tagged_writer(structure)).findings
        if f.rule_id == rules.PDF015.id
    )
    assert finding.details["problems"] == ["TR contains P", "Table contains TH"]


def test_tables_without_header_cells_are_warned_about(tmp_path: Path) -> None:
    structure = ["H1", ("Table", [("TR", ["TD"]), ("TR", ["TD"])])]
    report = audit(tmp_path, tagged_writer(structure))
    assert rules.PDF016.id in ids(report)
    assert rules.PDF016.id not in ids(
        audit(tmp_path, tagged_writer(["H1", ("Table", [("TR", ["TD"])])]))
    )


def test_an_annotation_without_a_link_element_is_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1"], link_annotations=1))
    finding = next(f for f in report.findings if f.rule_id == rules.PDF017.id)
    assert finding.details["count"] == 1
    assert rules.PDF017.id not in ids(audit(tmp_path, tagged_writer(["H1"])))


def test_a_link_element_that_refers_to_its_annotation_passes(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
    map_link(writer, link_elements(writer)[0], annotation_references(writer)[0])
    report = audit(tmp_path, writer)
    assert not ids(report) & {
        rules.PDF017.id,
        rules.PDF018.id,
        rules.PDF019.id,
    }
    assert measured(measurement(report, PdfLinkMeasurements).link_annotation_count) == 1
    assert measured(measurement(report, PdfLinkMeasurements).link_structure_element_count) == 1


def test_one_mapped_link_among_many_annotations_is_not_a_pass(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=20)
    map_link(writer, link_elements(writer)[0], annotation_references(writer)[0])
    report = audit(tmp_path, writer)
    finding = next(f for f in report.findings if f.rule_id == rules.PDF017.id)
    assert finding.details["count"] == 19
    annotations = finding.details["annotations"]
    assert isinstance(annotations, list)
    assert len(annotations) == 8


def test_a_link_element_without_any_annotation_reference_is_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", ("P", ["Link"])], link_annotations=1))
    assert {rules.PDF017.id, rules.PDF018.id} <= ids(report)
    assert next(f for f in report.findings if f.rule_id == rules.PDF018.id).details["count"] == 1


def test_one_annotation_shared_by_several_elements_on_its_page_is_a_wrapped_link(
    tmp_path: Path,
) -> None:
    writer = tagged_writer(["H1", ("P", ["Link", "Link"])], link_annotations=1)
    first, second = link_elements(writer)
    annotation = annotation_references(writer)[0]
    map_link(writer, first, annotation)
    map_link(writer, second, annotation)
    report = audit(tmp_path, writer)
    assert not ids(report) & {
        rules.PDF017.id,
        rules.PDF018.id,
        rules.PDF019.id,
    }


def test_a_link_without_any_description_is_an_error(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
    annotation = annotation_references(writer)[0]
    map_link(writer, link_elements(writer)[0], annotation)
    assert rules.PDF020.id not in ids(audit(tmp_path, writer))
    del dictionary(annotation)["/Contents"]
    finding = next(f for f in audit(tmp_path, writer).findings if f.rule_id == rules.PDF020.id)
    assert finding.details["count"] == 1


def test_an_alternate_description_on_the_link_element_describes_the_link(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
    annotation = annotation_references(writer)[0]
    element = link_elements(writer)[0]
    map_link(writer, element, annotation)
    del dictionary(annotation)["/Contents"]
    dictionary(element)[NameObject("/Alt")] = TextStringObject("Contact the author")
    assert rules.PDF020.id not in ids(audit(tmp_path, writer))


def test_a_mapping_declared_on_another_page_is_an_error(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
    other = writer.add_blank_page(width=100, height=100)
    map_link(
        writer,
        link_elements(writer)[0],
        annotation_references(writer)[0],
        page=other.indirect_reference,
    )
    finding = next(f for f in audit(tmp_path, writer).findings if f.rule_id == rules.PDF019.id)
    assert finding.severity.value == "error"
    assert finding.details["count"] == 1


def test_malformed_annotation_entries_are_skipped_not_fatal(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    page = writer.pages[0]
    page[NameObject("/Annots")] = NumberObject(5)
    assert rules.PDF001.id not in ids(audit(tmp_path, writer))
    page[NameObject("/Annots")] = ArrayObject([
        NumberObject(1),
        writer._add_object(NumberObject(2)),
    ])
    report = audit(tmp_path, writer)
    assert rules.PDF001.id not in ids(report)
    assert measured(measurement(report, PdfLinkMeasurements).link_annotation_count) == 0


def test_malformed_annotation_entries_do_not_abort_the_audit(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"], link_annotations=1)
    writer.pages[0][NameObject("/Annots")] = NumberObject(5)
    assert rules.PDF001.id not in ids(audit(tmp_path, writer))
    writer = tagged_writer(["H1"], link_annotations=1)
    annotations = writer.pages[0]["/Annots"]
    assert isinstance(annotations, ArrayObject)
    annotations.insert(0, NumberObject(7))
    assert rules.PDF001.id not in ids(audit(tmp_path, writer))
