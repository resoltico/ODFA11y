# SPDX-License-Identifier: MPL-2.0
"""Verify parsed PDF diagnostics with independent synthetic PDF objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf.generic import ArrayObject, BooleanObject, DictionaryObject, NameObject

from odfa11y.pdf import audit_pdfua

from .pdf_fixtures import annotation_references, link_elements, map_link, tagged_writer

if TYPE_CHECKING:
    from pathlib import Path

    from pypdf import PdfWriter

    from odfa11y.report import Report


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
    assert report.metadata["pdfua_part"] == 1
    assert report.metadata["structure_tags"] == {"H1": 1}
    assert report.metadata["extractable_text_characters"] > 0


@pytest.mark.parametrize(
    "mapping", [{"Illustration": "Figure"}, {"Illustration": "Picture", "Picture": "Figure"}]
)
def test_custom_figure_roles_require_alternative_text(
    tmp_path: Path, mapping: dict[str, str]
) -> None:
    report = audit(tmp_path, tagged_writer(["Illustration"], role_map=mapping))
    assert "PDF007" in ids(report)
    assert "PDF011" not in ids(report)


def test_figures_with_alternative_text_pass(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", "Figure"], figure_alt="A chart"))
    assert "PDF007" not in ids(report)


@pytest.mark.parametrize("mapping", [None, {"Custom": "Other", "Other": "Custom"}])
def test_unmapped_and_cyclic_roles_are_rejected(
    tmp_path: Path, mapping: dict[str, str] | None
) -> None:
    assert "PDF011" in ids(audit(tmp_path, tagged_writer(["Custom"], role_map=mapping)))


def test_false_marked_flag_is_rejected(tmp_path: Path) -> None:
    writer = tagged_writer()
    mark_info = writer.root_object["/MarkInfo"]
    assert isinstance(mark_info, DictionaryObject)
    mark_info[NameObject("/Marked")] = BooleanObject(value=False)
    assert "PDF003" in ids(audit(tmp_path, writer))


def test_invalid_pdf_returns_error_report(tmp_path: Path) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a PDF")
    assert ids(audit_pdfua(path)) == {"PDF000"}


def test_cyclic_structure_arrays_do_not_repeat_traversal(tmp_path: Path) -> None:
    writer = tagged_writer()
    structure = writer.root_object["/StructTreeRoot"]
    assert isinstance(structure, DictionaryObject)
    children = structure["/K"]
    assert isinstance(children, ArrayObject)
    children.append(writer._add_object(children))
    assert audit(tmp_path, writer).metadata["structure_tags"] == {"H1": 1}


def test_skipped_heading_levels_are_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", "H3", "H2"]))
    finding = next(f for f in report.findings if f.rule_id == "PDF012")
    assert finding.details["skips"] == ["H1 to H3"]
    assert "PDF012" not in ids(audit(tmp_path, tagged_writer(["H1", "H2", "H3", "H2"])))
    first = next(
        f for f in audit(tmp_path, tagged_writer(["H2", "H3"])).findings if f.rule_id == "PDF012"
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
    assert not ids(report) & {"PDF013", "PDF014", "PDF015"}, [f.as_dict() for f in report.findings]


def test_malformed_lists_are_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", ("L", ["P", ("LI", ["P"])])]))
    finding = next(f for f in report.findings if f.rule_id == "PDF013")
    assert finding.details["problems"] == ["L contains P", "LI contains P"]


def test_malformed_tables_are_reported(tmp_path: Path) -> None:
    structure = ["H1", ("Table", [("TH", []), ("TR", [("P", [])])])]
    finding = next(
        f for f in audit(tmp_path, tagged_writer(structure)).findings if f.rule_id == "PDF014"
    )
    assert finding.details["problems"] == ["TR contains P", "Table contains TH"]


def test_tables_without_header_cells_are_warned_about(tmp_path: Path) -> None:
    structure = ["H1", ("Table", [("TR", ["TD"]), ("TR", ["TD"])])]
    report = audit(tmp_path, tagged_writer(structure))
    assert "PDF015" in ids(report)
    assert "PDF015" not in ids(audit(tmp_path, tagged_writer(["H1", ("Table", [("TR", ["TD"])])])))


def test_an_annotation_without_a_link_element_is_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1"], link_annotations=1))
    finding = next(f for f in report.findings if f.rule_id == "PDF016")
    assert finding.details["count"] == 1
    assert "PDF016" not in ids(audit(tmp_path, tagged_writer(["H1"])))


def test_a_link_element_that_refers_to_its_annotation_passes(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
    map_link(writer, link_elements(writer)[0], annotation_references(writer)[0])
    report = audit(tmp_path, writer)
    assert not ids(report) & {"PDF016", "PDF017", "PDF018"}
    assert report.metadata["link_annotations"] == 1
    assert report.metadata["link_structure_elements"] == 1


def test_one_mapped_link_among_many_annotations_is_not_a_pass(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=20)
    map_link(writer, link_elements(writer)[0], annotation_references(writer)[0])
    report = audit(tmp_path, writer)
    finding = next(f for f in report.findings if f.rule_id == "PDF016")
    assert finding.details["count"] == 19
    assert len(finding.details["annotations"]) == 19


def test_a_link_element_without_any_annotation_reference_is_reported(tmp_path: Path) -> None:
    report = audit(tmp_path, tagged_writer(["H1", ("P", ["Link"])], link_annotations=1))
    assert {"PDF016", "PDF017"} <= ids(report)
    assert next(f for f in report.findings if f.rule_id == "PDF017").details["count"] == 1


def test_an_annotation_mapped_twice_is_an_error(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link", "Link"])], link_annotations=1)
    first, second = link_elements(writer)
    annotation = annotation_references(writer)[0]
    map_link(writer, first, annotation)
    map_link(writer, second, annotation)
    finding = next(f for f in audit(tmp_path, writer).findings if f.rule_id == "PDF018")
    assert finding.severity.value == "error"
    assert finding.details["count"] == 1


def test_a_mapping_declared_on_another_page_is_an_error(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
    other = writer.add_blank_page(width=100, height=100)
    map_link(
        writer,
        link_elements(writer)[0],
        annotation_references(writer)[0],
        page=other.indirect_reference,
    )
    assert "PDF018" in ids(audit(tmp_path, writer))
