# SPDX-License-Identifier: MPL-2.0
"""Evaluate precisely scoped exported-PDF capability observations."""

lazy from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream, StreamObject
lazy from pypdf.generic import DictionaryObject

from odfa11y.errors import ToolFailure
from odfa11y.pdf import validate_pdfua
from odfa11y.pdf.audit import PdfInspection, inspect_pdf
from odfa11y.pdf.reading.consumption import MAX_FORM_DEPTH, check_consumption
from odfa11y.pdf.structure_walk import build_tree, pdf_dictionary
from odfa11y.pdf.validate import PdfValidator
from odfa11y.report import exit_status
from odfa11y.rules import registry as rules

PROBE_IMAGES = 2
PROBE_HEADERS = 2


def _inspect(pdf: Path) -> PdfInspection:
    inspection = inspect_pdf(pdf)
    if any(f.rule is rules.PDF000 for f in inspection.report.findings):
        msg = "The capability probe PDF cannot be inspected."
        raise ToolFailure(msg)
    return inspection


def link_descriptions(
    pdf: Path,
    _validator: str | Path | None,
    _timeout: float,
    _validate: PdfValidator | None = None,
    *,
    expected: str,
) -> bool:
    """Require tagged link structure and the independently authored purpose string.

    Returns
    -------
    bool
        Whether the case's authored purpose survives in a link description.

    Raises
    ------
    ToolFailure
        The export contains no link annotation to inspect.

    """
    inspection = _inspect(pdf)
    report = inspection.report
    if inspection.structure is None or not inspection.structure.link_annotations:
        msg = "The capability probe PDF contains no hyperlink."
        raise ToolFailure(msg)
    tags = inspection.structure.tags if inspection.structure is not None else {}
    if not tags.get("Link") or any(
        f.rule
        in {rules.PDF003, rules.PDF004, rules.PDF016, rules.PDF017, rules.PDF018, rules.PDF019}
        for f in report.findings
    ):
        return False
    reader = PdfReader(pdf, strict=True)
    descriptions = [
        str(annotation.get_object().get("/Contents", ""))
        for page in reader.pages
        for annotation in page.get("/Annots", ())
    ]
    descriptions += [
        str(node.element.get("/Alt", ""))
        for node in build_tree(
            pdf_dictionary(pdf_dictionary(reader.trailer.get("/Root")).get("/StructTreeRoot"))
        ).walk()
        if node.role == "Link"
    ]
    return any(expected in value for value in descriptions)


def _images(
    stream: StreamObject | None,
    reader: PdfReader,
    resources: DictionaryObject,
    *,
    artifact: bool = False,
    depth: int = 0,
) -> tuple[int, int]:
    if depth > MAX_FORM_DEPTH:
        msg = "Probe image form traversal is incomplete."
        raise ToolFailure(msg)
    total = decorated = 0
    scopes = []
    for operands, operator in ContentStream(stream, reader).operations:
        if operator in {b"BMC", b"BDC"}:
            scopes.append(bool(operands and operands[0] == "/Artifact"))
        elif operator == b"EMC" and scopes:
            scopes.pop()
        elif operator == b"Do" and operands:
            objects = pdf_dictionary(resources.get("/XObject"))
            obj = objects.get(operands[0])
            obj = obj.get_object() if obj is not None else None
            hidden = artifact or any(scopes)
            if isinstance(obj, StreamObject) and obj.get("/Subtype") == "/Image":
                total += 1
                decorated += int(hidden)
            elif isinstance(obj, StreamObject) and obj.get("/Subtype") == "/Form":
                count, marked = _images(
                    obj,
                    reader,
                    pdf_dictionary(obj.get("/Resources", resources)),
                    artifact=hidden,
                    depth=depth + 1,
                )
                total += count
                decorated += marked
    return total, decorated


def decorative_role(
    pdf: Path, _validator: str | Path | None, _timeout: float, _validate: PdfValidator | None = None
) -> bool:
    """Require two painted images with only the decorative peer marked as an artifact.

    Returns
    -------
    bool
        Whether one described Figure and a painted artifact image survive export.

    """
    inspection = _inspect(pdf)
    report = inspection.report
    reader = PdfReader(pdf, strict=True)
    check_consumption(reader)
    counts = [
        _images(page.get_contents(), reader, pdf_dictionary(page.get("/Resources")))
        for page in reader.pages
    ]
    total, artifacts = sum(c[0] for c in counts), sum(c[1] for c in counts)
    tags = inspection.structure.tags if inspection.structure is not None else {}
    return (
        total == PROBE_IMAGES
        and artifacts == 1
        and tags.get("Figure") == 1
        and not any(f.rule is rules.PDF007 for f in report.findings)
    )


def writer_header_columns(
    pdf: Path, _validator: str | Path | None, _timeout: float, _validate: PdfValidator | None = None
) -> bool:
    """Require semantic header cells for both rows of the column-header case.

    Returns
    -------
    bool
        Whether a two-row table exports both declared column headers as TH.

    """
    inspection = _inspect(pdf)
    tags = inspection.structure.tags if inspection.structure is not None else {}
    return tags.get("Table", 0) >= 1 and tags.get("TH", 0) >= PROBE_HEADERS


def math_tagging(
    pdf: Path, _validator: str | Path | None, _timeout: float, _validate: PdfValidator | None = None
) -> bool:
    """Require tagged, reconciled content in the expression-only Math case.

    Returns
    -------
    bool
        Whether the Math export passes basic structural inspection with a real structure tree.

    """
    inspection = _inspect(pdf)
    report = inspection.report
    return (report.error_count == 0) and bool(inspection.structure and inspection.structure.tags)


def calc_pdfua(
    pdf: Path, validator: str | Path | None, timeout: float, validate: PdfValidator | None = None
) -> bool:
    """Check the small semantic Calc table with PDF inspection and veraPDF.

    Returns
    -------
    bool
        Whether this exact Calc export passes both independent checks.

    """
    inspection = _inspect(pdf)
    report = inspection.report
    return (
        bool((inspection.structure.tags if inspection.structure is not None else {}).get("Table"))
        and exit_status([report], strict=True) == 0
        and (validate or validate_pdfua)(pdf, executable=validator, timeout=timeout).compliant
    )
