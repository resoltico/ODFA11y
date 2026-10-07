# SPDX-License-Identifier: MPL-2.0
"""Verify parsed PDF diagnostics with independent synthetic PDF objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf.generic import ArrayObject, BooleanObject, DictionaryObject, NameObject

from odfa11y.pdf import audit_pdfua

from .pdf_fixtures import tagged_writer

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


def test_link_annotations_need_link_structure_elements(tmp_path: Path) -> None:
    assert "PDF016" in ids(audit(tmp_path, tagged_writer(["H1"], link_annotations=1)))
    tagged = audit(tmp_path, tagged_writer(["H1", ("P", ["Link"])], link_annotations=1))
    assert "PDF016" not in ids(tagged)
    assert tagged.metadata["link_structure_elements"] == 1
    assert "PDF016" not in ids(audit(tmp_path, tagged_writer(["H1"])))
