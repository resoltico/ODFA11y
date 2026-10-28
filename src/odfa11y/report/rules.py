# SPDX-License-Identifier: MPL-2.0
"""The registry of stable finding rules: the one source of id, severity and decision kinds."""

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
    """A stable check identity; decision kinds name the human answers that can address it."""

    id: str
    severity: Severity
    category: Category
    title: str
    decision_kinds: tuple[str, ...] = ()


RULES: dict[str, Rule] = {}


def _rule(
    rule_id: str,
    severity: Severity,
    category: Category,
    title: str,
    decision_kinds: tuple[str, ...] = (),
) -> Rule:
    rule = Rule(rule_id, severity, category, title, decision_kinds)
    RULES[rule_id] = rule
    return rule


ERROR, WARNING, INFO = Severity.ERROR, Severity.WARNING, Severity.INFO
PKG, XML, ODF = Category.PACKAGE, Category.XML, Category.ODF
META, SEM, LAY, LNK = Category.METADATA, Category.SEMANTICS, Category.LAYOUT, Category.LINKS
STYLE, PDF, VAL, FID = Category.STYLE, Category.PDF, Category.VALIDATOR, Category.FIDELITY

PKG000 = _rule("PKG000", ERROR, PKG, "Source is not a readable ODF package or flat XML document.")
PKG001 = _rule("PKG001", WARNING, PKG, "The document does not declare its media type.")
PKG002 = _rule("PKG002", WARNING, PKG, "An optional package member is missing.")
PKG003 = _rule("PKG003", ERROR, PKG, "mimetype is not the first ZIP member.")
PKG004 = _rule("PKG004", ERROR, PKG, "mimetype is compressed.")
PKG005 = _rule("PKG005", ERROR, PKG, "A member the document needs is missing.")
PKG006 = _rule("PKG006", ERROR, PKG, "ZIP member names are duplicated.")
PKG007 = _rule("PKG007", ERROR, PKG, "A ZIP member name is absolute or escapes its directory.")
PKG008 = _rule("PKG008", WARNING, PKG, "Declared signatures are unverified.")
PKG009 = _rule("PKG009", ERROR, PKG, "Manifest encryption prevents complete inspection.")
XML001 = _rule("XML001", ERROR, XML, "A required XML member cannot be parsed.")
ODF001 = _rule(
    "ODF001",
    ERROR,
    ODF,
    "Package members declare different ODF versions.",
    ("document.odf_version",),
)
ODF002 = _rule("ODF002", ERROR, ODF, "Manifest root file-entry '/' is missing.")
ODF003 = _rule(
    "ODF003",
    ERROR,
    ODF,
    "Manifest root file-entry version differs from the document version.",
    ("document.odf_version",),
)
ODF004 = _rule("ODF004", ERROR, ODF, "Manifest root media type differs from the document's.")
ODF005 = _rule("ODF005", ERROR, ODF, "The media type is not an OpenDocument document type.")
ODF006 = _rule("ODF006", ERROR, ODF, "The document body does not match its media type.")
ODF007 = _rule("ODF007", WARNING, ODF, "The file extension does not match the media type.")
ODF008 = _rule("ODF008", WARNING, ODF, "The document kind is deprecated.")
ODF009 = _rule("ODF009", INFO, ODF, "No semantic audit exists for this document family.")
ODF010 = _rule("ODF010", ERROR, ODF, "A flat XML document's root is not office:document.")
ODF011 = _rule("ODF011", ERROR, ODF, "A package's content root is not office:document-content.")
SCHEMA001 = _rule("SCHEMA001", WARNING, ODF, "A member does not validate against the ODF schema.")
SCHEMA002 = _rule("SCHEMA002", INFO, ODF, "No ODF schema is bundled for the declared version.")
NATIVE001 = _rule(
    "NATIVE001", WARNING, ODF, "Native resource declarations are unresolved or unestablished."
)
NATIVE002 = _rule(
    "NATIVE002", WARNING, ODF, "Pipeline export cannot preserve filename/path fields."
)
META001 = _rule(
    "META001", ERROR, META, "Document title metadata is missing.", ("document.metadata",)
)
META002 = _rule(
    "META002", ERROR, META, "Document language is not declared.", ("document.metadata",)
)
META003 = _rule(
    "META003",
    WARNING,
    META,
    "Metadata and default style languages disagree.",
    ("document.metadata",),
)
META004 = _rule(
    "META004", WARNING, META, "Document language syntax or default-style target is unresolved."
)
HEADING001 = _rule(
    "HEADING001", ERROR, SEM, "Heading has no valid outline level.", ("heading.level",)
)
HEADING002 = _rule(
    "HEADING002",
    ERROR,
    SEM,
    "Heading hierarchy starts too deep or skips a level.",
    ("heading.level",),
)
HEADING003 = _rule("HEADING003", WARNING, SEM, "Heading text resembles manually typed numbering.")
HEADING004 = _rule("HEADING004", INFO, SEM, "No structural headings were found.")
NOTE001 = _rule(
    "NOTE001", WARNING, SEM, "Notes or annotations need relationship and reading-order review."
)
REVISION001 = _rule("REVISION001", WARNING, SEM, "Tracked revision scope requires review.")
HIDDEN001 = _rule(
    "HIDDEN001", WARNING, SEM, "Hidden or conditional content requires visibility review."
)
STYLE001 = _rule("STYLE001", WARNING, SEM, "Paragraph style scope or properties are unresolved.")
GRAPHIC003 = _rule(
    "GRAPHIC003",
    ERROR,
    SEM,
    "Graphic has neither accessible title nor description.",
    ("graphic.alternative",),
)
TABLE001 = _rule("TABLE001", WARNING, SEM, "Merged table cells need header-relationship review.")
TABLE002 = _rule("TABLE002", ERROR, SEM, "Table grid or header bands cannot be resolved safely.")
TABLE003 = _rule(
    "TABLE003", WARNING, SEM, "Data-like table has no semantic headers.", ("table.headers",)
)
LINK001 = _rule(
    "LINK001",
    WARNING,
    LNK,
    "Visible URL or email address is not a hyperlink.",
    ("text.linkify_addresses",),
)
LAYOUT001 = _rule(
    "LAYOUT001",
    INFO,
    LAY,
    "Empty paragraphs may be visual spacers.",
    ("text.remove_spacers",),
)
STYLE002 = _rule("STYLE002", ERROR, STYLE, "Blinking text styling is declared.")

SHEET001 = _rule("SHEET001", ERROR, SEM, "Sheet has no name.")
SHEET002 = _rule("SHEET002", WARNING, SEM, "Sheet keeps its default name.", ("sheet.name",))
TABLE004 = _rule("TABLE004", WARNING, SEM, "Data sheet marks no header rows.")
TABLE005 = _rule("TABLE005", WARNING, SEM, "Data sheet merges cells.")
LINK002 = _rule("LINK002", WARNING, LNK, "Hyperlink text is a raw address.")
SHEET007 = _rule("SHEET007", WARNING, SEM, "Empty sheet follows the last sheet with content.")

PAGE001 = _rule("PAGE001", ERROR, SEM, "Pages are missing, unnamed or ambiguously named.")
PAGE002 = _rule("PAGE002", WARNING, SEM, "Page has no accessible title.", ("page.metadata",))
GRAPHIC005 = _rule(
    "GRAPHIC005",
    WARNING,
    SEM,
    "Nontext shape needs a meaning/decorative-content decision.",
    ("graphic.alternative",),
)
PAGE003 = _rule(
    "PAGE003", ERROR, SEM, "Navigation order is incomplete or ambiguous.", ("page.navigation",)
)
PAGE004 = _rule(
    "PAGE004", WARNING, SEM, "Page has no explicit navigation order.", ("page.navigation",)
)
LINK003 = _rule("LINK003", ERROR, LNK, "Hyperlink has no readable purpose.", ("link.description",))


MATH001 = _rule("MATH001", ERROR, SEM, "Native mathematical expression is missing or unsupported.")
MATH002 = _rule(
    "MATH002", ERROR, SEM, "Formula has no spoken alternative.", ("formula.alternative",)
)
MATH003 = _rule("MATH003", WARNING, SEM, "Formula references external content requiring review.")

CHART001 = _rule("CHART001", ERROR, SEM, "Chart body or data series is missing or ambiguous.")
CHART002 = _rule(
    "CHART002", WARNING, SEM, "Chart has no identifying title.", ("document.metadata",)
)
CHART003 = _rule(
    "CHART003", ERROR, SEM, "Chart has no supplied document description.", ("document.metadata",)
)
CHART004 = _rule("CHART004", ERROR, SEM, "Local chart range does not match its declared data grid.")
CHART005 = _rule(
    "CHART005", WARNING, SEM, "Chart data provider or range cannot be verified locally."
)
CHART006 = _rule("CHART006", WARNING, SEM, "Chart labels or data ordering need review.")

IMAGE005 = _rule(
    "IMAGE005", WARNING, SEM, "SVG declares active or external content requiring native review."
)
IMAGE004 = _rule("IMAGE004", ERROR, SEM, "Image payload is malformed or unsafe to inspect.")
IMAGE001 = _rule("IMAGE001", ERROR, SEM, "Image body does not contain one supported graphic frame.")
IMAGE003 = _rule(
    "IMAGE003", WARNING, SEM, "Image resource is external, unavailable or not embedded."
)

BASE001 = _rule("BASE001", ERROR, SEM, "Database body, connection or embedded storage is missing.")
BASE002 = _rule("BASE002", WARNING, SEM, "Database has external connection declarations.")
BASE003 = _rule(
    "BASE003", WARNING, SEM, "Database stores authentication information requiring privacy review."
)
BASE004 = _rule(
    "BASE004",
    WARNING,
    SEM,
    "Database object description is missing or ambiguous.",
    ("database.description",),
)
BASE005 = _rule(
    "BASE005", WARNING, SEM, "Database has executable scripts requiring offline review."
)
BASE006 = _rule("BASE006", INFO, SEM, "Queries, forms or reports require native semantic review.")

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
PDF010 = _rule(
    "PDF010", ERROR, PDF, "No extractable text or inspected described graphical content was found."
)
PDF011 = _rule("PDF011", ERROR, PDF, "A custom structure role does not resolve to a standard role.")
PDF012 = _rule("PDF012", ERROR, PDF, "Heading structure starts too deep or skips a level.")
PDF013 = _rule("PDF013", ERROR, PDF, "List structure is malformed.")
PDF014 = _rule("PDF014", ERROR, PDF, "Table structure is malformed.")
PDF015 = _rule("PDF015", WARNING, PDF, "Table has no header cells.")
PDF016 = _rule("PDF016", WARNING, PDF, "A link annotation is not represented by a Link element.")
PDF017 = _rule("PDF017", WARNING, PDF, "A Link structure element refers to no link annotation.")
PDF018 = _rule("PDF018", ERROR, PDF, "A link annotation is referenced from another page.")
PDF019 = _rule("PDF019", ERROR, PDF, "A link has no alternate description.")
PDF020 = _rule(
    "PDF020", ERROR, PDF, "Marked content in an inspected stream is not part of the structure tree."
)
PDF021 = _rule(
    "PDF021",
    WARNING,
    PDF,
    "A structure element refers to marked content its inspected stream does not have.",
)
PDF022 = _rule("PDF022", WARNING, PDF, "Marked content is referenced by more than one element.")
PDF023 = _rule("PDF023", ERROR, PDF, "Text is shown outside tagged content and artifacts.")
VERA000 = _rule("VERA000", WARNING, VAL, "The requested veraPDF validator is unavailable.")
VERA001 = _rule("VERA001", ERROR, VAL, "veraPDF reports a failed PDF/UA-1 rule.")

FID001 = _rule("FID001", ERROR, FID, "Page count differs.")
FID002 = _rule("FID002", ERROR, FID, "Page dimensions differ.")
FID003 = _rule("FID003", ERROR, FID, "Document text differs.")
FID004 = _rule("FID004", ERROR, FID, "A source link is missing or changed.")
FID005 = _rule("FID005", ERROR, FID, "Rendered page differs beyond the tolerance.")
FID006 = _rule("FID006", INFO, FID, "Links were added.")
FID007 = _rule("FID007", ERROR, FID, "A page is too large to render for comparison.")


GRAPHIC001 = _rule("GRAPHIC001", WARNING, SEM, "Graphic decorative role is unresolved or unsafe.")
GRAPHIC002 = _rule(
    "GRAPHIC002", WARNING, SEM, "Decorative graphic retains authored alternative metadata."
)


LIST001 = _rule("LIST001", ERROR, SEM, "List membership or nesting is structurally invalid.")
LIST002 = _rule("LIST002", ERROR, SEM, "List continuation target is broken, ambiguous or cyclic.")
LIST003 = _rule("LIST003", WARNING, SEM, "List counter continuation requires native review.")
LIST004 = _rule("LIST004", WARNING, SEM, "Paragraph resembles a manually simulated list.")
