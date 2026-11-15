# SPDX-License-Identifier: MPL-2.0
"""Protect spreadsheet formulas, values, references, geometry and hidden content."""

from lxml import etree

from odfa11y.concepts import graphic_normalization, protected_xml
from odfa11y.families.spreadsheet.sheets import sheet_name, sheets
from odfa11y.odf import Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.odf.styles import normalize_generated

SHEET_TAG = "sheet\t"


def sheet_snapshot(document: OdfDocument) -> tuple[str, ...]:
    """Bind every sheet to its complete content, except name and graphic descriptions.

    Returns
    -------
    tuple[str, ...]
        Sheet-name entries followed by protected XML digests, preserving ordering,
        formulas, values, references, geometry, repeats and hidden content.

    """
    entries: list[str] = []
    for sheet in sheets(document.tree(Part.CONTENT)):
        entries.extend((
            f"{SHEET_TAG}{sheet_name(sheet)}",
            "content\t" + sheet_identity(document, sheet),
        ))
    return tuple(entries)


def sheets_preserved(before: tuple[str, ...], after: tuple[str, ...]) -> bool:
    """Allow sheet names to change and nothing else to differ.

    Returns
    -------
    bool
        Whether both snapshots have the same sheets in the same order with the same protected
        content; sheet content must remain identical.

    """
    return len(before) == len(after) and all(
        old == new or (old.startswith(SHEET_TAG) and new.startswith(SHEET_TAG))
        for old, new in zip(before, after, strict=True)
    )


def sheet_identity(document: OdfDocument, sheet: etree._Element) -> str:
    """Bind preserved sheet content independently of editable accessibility metadata.

    Returns
    -------
    str
        Full protected-content digest; sheet order is addressed separately.

    """
    return protected_xml(
        normalize_generated(sheet, graphic_normalization(document)),
        omitted_root_attributes=(xml_names.TABLE_NAME,),
        omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
        omitted_element_attributes={
            qn(ns, "a"): (xml_names.OFFICE_TITLE,) for ns in ("draw", "text")
        },
    )


def sheet_fingerprint(document: OdfDocument, sheet: etree._Element) -> Fingerprint:
    """Bind a rename to the same preserved identity used by family guards.

    Returns
    -------
    str
        Reviewed target fingerprint, stable after allowed accessibility edits.

    """
    return Fingerprint.from_digest(sheet_identity(document, sheet))
