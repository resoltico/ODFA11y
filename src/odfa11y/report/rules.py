# SPDX-License-Identifier: MPL-2.0
"""The registry of stable finding rules: the one source of id, severity and remedy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """Classify findings by their effect on acceptance."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Category(StrEnum):
    """Group rules by the property they concern."""

    PACKAGE = "package"
    XML = "xml"
    ODF = "odf"
    METADATA = "metadata"
    SEMANTICS = "semantics"
    LAYOUT = "layout"
    LINKS = "links"
    STYLE = "style"
    PDF = "pdf"
    VALIDATOR = "validator"
    FIDELITY = "fidelity"


@dataclass(frozen=True, slots=True)
class Rule:
    """A stable check identity; ``remedy`` names the configuration key that addresses it."""

    id: str
    severity: Severity
    category: Category
    title: str
    remedy: str | None = None


RULES: dict[str, Rule] = {}


def _rule(
    rule_id: str,
    severity: Severity,
    category: Category,
    title: str,
    remedy: str | None = None,
) -> Rule:
    rule = Rule(rule_id, severity, category, title, remedy)
    RULES[rule_id] = rule
    return rule


ERROR, WARNING, INFO = Severity.ERROR, Severity.WARNING, Severity.INFO
PKG, XML, ODF = Category.PACKAGE, Category.XML, Category.ODF
META, SEM, LAY, LNK = Category.METADATA, Category.SEMANTICS, Category.LAYOUT, Category.LINKS
STYLE, PDF, VAL, FID = Category.STYLE, Category.PDF, Category.VALIDATOR, Category.FIDELITY

PKG000 = _rule("PKG000", ERROR, PKG, "Source is not a readable ODT/ZIP package.")
PKG001 = _rule("PKG001", ERROR, PKG, "Required mimetype member is missing.")
PKG002 = _rule("PKG002", ERROR, PKG, "MIME type is not application/vnd.oasis.opendocument.text.")
PKG003 = _rule("PKG003", ERROR, PKG, "mimetype is not the first ZIP member.")
PKG004 = _rule("PKG004", ERROR, PKG, "mimetype is compressed.")
PKG005 = _rule("PKG005", ERROR, PKG, "A required XML member is missing.")
PKG006 = _rule("PKG006", ERROR, PKG, "ZIP member names are duplicated.")
PKG007 = _rule("PKG007", ERROR, PKG, "A ZIP member name is absolute or escapes its directory.")
XML001 = _rule("XML001", ERROR, XML, "A required XML member cannot be parsed.")
ODF001 = _rule(
    "ODF001", ERROR, ODF, "Package members declare different ODF versions.", "document.odf_version"
)
ODF002 = _rule("ODF002", ERROR, ODF, "Manifest root file-entry '/' is missing.")
ODF003 = _rule(
    "ODF003",
    ERROR,
    ODF,
    "Manifest root file-entry version differs from the document version.",
    "document.odf_version",
)
ODF004 = _rule("ODF004", ERROR, ODF, "Manifest root media type is not the ODT media type.")
ODF900 = _rule("ODF900", WARNING, ODF, "A member does not validate against the ODF schema.")
ODF905 = _rule("ODF905", INFO, ODF, "No ODF schema is bundled for the declared version.")
META001 = _rule("META001", ERROR, META, "Document title metadata is missing.", "document.title")
META002 = _rule("META002", ERROR, META, "Document language is not declared.", "document.language")
META003 = _rule(
    "META003",
    WARNING,
    META,
    "Metadata and default paragraph-style languages disagree.",
    "document.language",
)
SEM001 = _rule("SEM001", ERROR, SEM, "Heading has no valid outline level.")
SEM002 = _rule("SEM002", ERROR, SEM, "Heading hierarchy starts too deep or skips a level.")
SEM003 = _rule("SEM003", WARNING, SEM, "Heading text resembles manually typed numbering.")
SEM004 = _rule("SEM004", INFO, SEM, "No structural headings were found.")
SEM005 = _rule("SEM005", WARNING, SEM, "Footnotes or endnotes need reading-order review.")
IMG001 = _rule(
    "IMG001", ERROR, SEM, "Graphic has neither accessible title nor description.", "alt_text"
)
TBL001 = _rule("TBL001", ERROR, SEM, "Table has merged or split cells.")
TBL002 = _rule("TBL002", WARNING, SEM, "Data-like table has no header rows.", "table_headers")
LNK001 = _rule(
    "LNK001",
    WARNING,
    LNK,
    "Visible URL or email address is not a hyperlink.",
    "remediation.linkify_plain_addresses",
)
LAY001 = _rule(
    "LAY001",
    INFO,
    LAY,
    "Empty paragraphs may be visual spacers.",
    "remediation.remove_empty_spacers",
)
STYLE001 = _rule("STYLE001", ERROR, STYLE, "Blinking text styling is declared.")

PDF000 = _rule("PDF000", ERROR, PDF, "PDF cannot be opened or strictly inspected.")
PDF001 = _rule("PDF001", ERROR, PDF, "Document title is missing.")
PDF002 = _rule("PDF002", ERROR, PDF, "Catalog language is missing.")
PDF003 = _rule("PDF003", ERROR, PDF, "PDF is not marked as tagged.")
PDF004 = _rule("PDF004", ERROR, PDF, "Structure tree root is absent or empty.")
PDF005 = _rule("PDF005", WARNING, PDF, "Viewer preferences do not display the title.")
PDF006 = _rule("PDF006", ERROR, PDF, "XMP metadata does not declare PDF/UA part 1.")
PDF007 = _rule("PDF007", ERROR, PDF, "A Figure structure element has no alternative text.")
PDF008 = _rule("PDF008", INFO, PDF, "No numbered heading structure elements were found.")
PDF009 = _rule("PDF009", ERROR, PDF, "PDF has no pages.")
PDF010 = _rule("PDF010", ERROR, PDF, "No extractable text was found.")
PDF011 = _rule("PDF011", ERROR, PDF, "A custom structure role does not resolve to a standard role.")
PDF012 = _rule("PDF012", ERROR, PDF, "Heading structure starts too deep or skips a level.")
PDF013 = _rule("PDF013", ERROR, PDF, "List structure is malformed.")
PDF014 = _rule("PDF014", ERROR, PDF, "Table structure is malformed.")
PDF015 = _rule("PDF015", WARNING, PDF, "Table has no header cells.")
PDF016 = _rule("PDF016", WARNING, PDF, "Link annotations have no Link structure elements.")
VERA000 = _rule("VERA000", WARNING, VAL, "The requested veraPDF validator is unavailable.")
VERA001 = _rule("VERA001", ERROR, VAL, "veraPDF reports a failed PDF/UA-1 rule.")

FID001 = _rule("FID001", ERROR, FID, "Page count differs.")
FID002 = _rule("FID002", ERROR, FID, "Page dimensions differ.")
FID003 = _rule("FID003", ERROR, FID, "Document text differs.")
FID004 = _rule("FID004", ERROR, FID, "A source link is missing or changed.")
FID005 = _rule("FID005", ERROR, FID, "Rendered page differs beyond the tolerance.")
FID006 = _rule("FID006", INFO, FID, "Links were added.")
FID007 = _rule("FID007", ERROR, FID, "A page is too large to render for comparison.")
