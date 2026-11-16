# SPDX-License-Identifier: MPL-2.0
"""Evaluate precisely scoped exported-PDF capability observations."""

lazy from pathlib import Path

from odfa11y.errors import ToolFailure
from odfa11y.pdf.audit import PdfInspection, inspect_pdf
from odfa11y.pdf.validation import PdfValidator
from odfa11y.report import exit_status
from odfa11y.rules import registry as rules

PROBE_IMAGES = 2
PROBE_HEADERS = 2


def _inspect(pdf: Path) -> PdfInspection:
    inspection = inspect_pdf(pdf)
    if any(f.rule is rules.PDF001 for f in inspection.report.findings):
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
        in {rules.PDF004, rules.PDF005, rules.PDF017, rules.PDF018, rules.PDF019, rules.PDF020}
        for f in report.findings
    ):
        return False
    return any(expected in value for value in inspection.link_descriptions)


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
    total, artifacts = inspection.image_operations, inspection.artifact_image_operations
    tags = inspection.structure.tags if inspection.structure is not None else {}
    return (
        total == PROBE_IMAGES
        and artifacts == 1
        and tags.get("Figure") == 1
        and not any(f.rule is rules.PDF008 for f in report.findings)
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
    if validate is None:
        message = "Independent PDF/UA validation is unavailable for this capability probe."
        raise ToolFailure(message)
    inspection = _inspect(pdf)
    report = inspection.report
    return (
        bool((inspection.structure.tags if inspection.structure is not None else {}).get("Table"))
        and exit_status([report], strict=True) == 0
        and validate(pdf, executable=validator, timeout=timeout).compliant
    )
