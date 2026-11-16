# SPDX-License-Identifier: MPL-2.0
"""Protect spreadsheet formulas, values, references, geometry and hidden content."""

from lxml import etree

from odfa11y.concepts import graphic_normalization, protected_xml
from odfa11y.odf import names as xml_names
from odfa11y.odf import qn
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.odf.styles import normalize_generated


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
    """Bind a rename to its protected source content.

    Returns
    -------
    str
        Reviewed target fingerprint, stable after allowed accessibility edits.

    """
    return Fingerprint.from_digest(sheet_identity(document, sheet))
