# SPDX-License-Identifier: MPL-2.0
"""Rule identities, severities and the meanings of observed conditions."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from odfa11y.rules.details import DetailList, DetailText, detail_contract


class Severity(StrEnum):
    """Classify findings by their effect on acceptance."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.ERROR: "A finding prevents acceptance under every profile.",
            self.WARNING: "A finding requires review and prevents strict acceptance.",
            self.INFO: "An observation provides context without preventing acceptance.",
        }[self]


@dataclass(frozen=True, slots=True)
class Rule:
    """A stable check identity and the condition it reports."""

    id: str
    severity: Severity
    title: str
    details: object

    @property
    def category(self) -> str:
        """The concern category derived from the authoritative concept prefix."""
        return self.id.rstrip("0123456789").lower()


RULES: dict[str, Rule] = {}


def _rule(
    rule_id: str,
    severity: Severity,
    title: str,
    *,
    detail_fields: dict[str, object] | None = None,
) -> Rule:
    rule = Rule(rule_id, severity, title, detail_contract(rule_id, detail_fields or {}))
    RULES[rule_id] = rule
    return rule


ERROR, WARNING, INFO = Severity.ERROR, Severity.WARNING, Severity.INFO


PKG001 = _rule("PKG001", ERROR, "Source is not a readable ODF package or flat XML document.")
PKG002 = _rule("PKG002", WARNING, "The document has no office:mimetype attribute.")
PKG003 = _rule(
    "PKG003", WARNING, "Package has no mimetype member; tools cannot recognise its type without it."
)
PKG004 = _rule(
    "PKG004",
    WARNING,
    "mimetype is not exactly an ASCII media type (stray whitespace or non-ASCII bytes).",
)
PKG005 = _rule("PKG005", WARNING, "An optional package member is missing.")
PKG006 = _rule("PKG006", ERROR, "mimetype is not the first ZIP member.")
PKG007 = _rule("PKG007", ERROR, "mimetype is compressed.")
PKG008 = _rule("PKG008", ERROR, "A member the document needs is missing.")
PKG009 = _rule(
    "PKG009", ERROR, "ZIP member names are duplicated.", detail_fields={"duplicates": DetailList}
)
PKG010 = _rule(
    "PKG010",
    ERROR,
    "A ZIP member name is absolute or escapes its directory.",
    detail_fields={"names": DetailList},
)
PKG011 = _rule(
    "PKG011", WARNING, "Declared signatures are unverified.", detail_fields={"members": DetailList}
)
PKG012 = _rule("PKG012", ERROR, "Manifest encryption prevents complete inspection.")
XML001 = _rule("XML001", ERROR, "A required XML member cannot be parsed.")
ODF001 = _rule(
    "ODF001",
    ERROR,
    "Package members declare different ODF versions.",
    detail_fields={"versions": dict[str, DetailText | None]},
)
ODF002 = _rule("ODF002", ERROR, "Manifest root file-entry '/' is missing.")
ODF003 = _rule("ODF003", ERROR, "Manifest version differs from the document version.")
ODF004 = _rule(
    "ODF004", ERROR, "Manifest root file-entry version differs from the document version."
)
ODF005 = _rule("ODF005", ERROR, "Manifest root media type differs from the document's.")
ODF006 = _rule(
    "ODF006",
    ERROR,
    "The media type is not an OpenDocument document type.",
    detail_fields={"media_type": DetailText | None, "declared_by": DetailText | None},
)
ODF007 = _rule(
    "ODF007",
    ERROR,
    "The document body does not match its media type.",
    detail_fields={"body": DetailText | None, "expected": DetailText | None},
)
ODF008 = _rule("ODF008", WARNING, "The file extension does not match the media type.")
ODF009 = _rule("ODF009", WARNING, "The document kind is deprecated.")
ODF010 = _rule("ODF010", INFO, "No semantic audit exists for this document family.")
ODF011 = _rule("ODF011", ERROR, "A flat XML document's root is not office:document.")
ODF012 = _rule("ODF012", ERROR, "A package's content root is not office:document-content.")
SCHEMA001 = _rule(
    "SCHEMA001",
    WARNING,
    "A member does not validate against the ODF schema.",
    detail_fields={"count": int, "violations": DetailList},
)
SCHEMA002 = _rule("SCHEMA002", INFO, "No ODF schema is bundled for the declared version.")
NATIVE001 = _rule(
    "NATIVE001",
    WARNING,
    "Native resource declarations are unresolved or unestablished.",
    detail_fields={"count": int},
)
NATIVE002 = _rule(
    "NATIVE002",
    WARNING,
    "Pipeline export cannot preserve filename/path fields.",
    detail_fields={"count": int},
)
META001 = _rule("META001", ERROR, "Document title metadata is missing.")
META002 = _rule("META002", ERROR, "Document language is not declared.")
META003 = _rule(
    "META003",
    WARNING,
    "Metadata and default style languages disagree.",
    detail_fields={"metadata": DetailText | None, "default_style": DetailText | None},
)
META004 = _rule(
    "META004",
    WARNING,
    "Document language syntax or default-style target is unresolved.",
    detail_fields={"metadata": DetailText | None, "default_style": DetailText | None},
)
HEADING001 = _rule(
    "HEADING001",
    ERROR,
    "Heading has no valid outline level.",
    detail_fields={"text": DetailText | None},
)
HEADING002 = _rule(
    "HEADING002",
    ERROR,
    "The first heading starts below level one.",
    detail_fields={"text": DetailText | None},
)
HEADING003 = _rule(
    "HEADING003",
    ERROR,
    "Heading hierarchy skips an outline level.",
    detail_fields={"text": DetailText | None},
)
HEADING004 = _rule(
    "HEADING004",
    WARNING,
    "Heading text resembles manually typed numbering.",
    detail_fields={"text": DetailText | None},
)
HEADING005 = _rule("HEADING005", INFO, "No structural headings were found.")
NOTE001 = _rule(
    "NOTE001",
    WARNING,
    "Notes or annotations need relationship and reading-order review.",
    detail_fields={"content_count": int, "count": int, "classes": dict[str, int]},
)
REVISION001 = _rule("REVISION001", ERROR, "Tracked-region identities are missing or contradictory.")
REVISION002 = _rule("REVISION002", ERROR, "Tracked-region change-mark relationship is invalid.")
REVISION003 = _rule("REVISION003", ERROR, "Change mark has no unique tracked-region declaration.")
REVISION004 = _rule(
    "REVISION004", WARNING, "Tracked declaration has no established current-flow anchor."
)
REVISION005 = _rule(
    "REVISION005", WARNING, "Change anchor is inside an unestablished visibility context."
)
ORDER001 = _rule(
    "ORDER001",
    WARNING,
    "Visibility declarations are incomplete or contradictory.",
    detail_fields={"native_editing": DetailText},
)
ORDER002 = _rule(
    "ORDER002",
    WARNING,
    "Declared layout requires native reading-order review.",
    detail_fields={"kind": DetailText | None, "count": int, "scope": DetailText},
)
REVISION006 = _rule(
    "REVISION006",
    WARNING,
    "Tracked revision scope requires review.",
    detail_fields={"regions": int, "markers": int},
)
ORDER003 = _rule(
    "ORDER003",
    WARNING,
    "Hidden or conditional content requires visibility review.",
    detail_fields={
        "sheets": DetailList,
        "rows": int,
        "columns": int,
        "contexts": int,
        "hidden_pages": int,
        "hidden_layer_declarations": int,
    },
)
STYLE001 = _rule(
    "STYLE001",
    WARNING,
    "Paragraph style scope or properties are unresolved.",
    detail_fields={"styles": dict[str, DetailText]},
)
GRAPHIC001 = _rule(
    "GRAPHIC001",
    ERROR,
    "Graphic has neither accessible title nor description.",
    detail_fields={
        "frame": DetailText | None,
        "href": DetailText | None,
        "page": DetailText | None,
        "shape_identities": DetailList,
        "shape": DetailText | None,
    },
)
TABLE001 = _rule(
    "TABLE001",
    WARNING,
    "Table intent or header relationships require native review.",
    detail_fields={"classification": DetailText | None, "native_editing": DetailText | None},
)
TABLE002 = _rule(
    "TABLE002",
    ERROR,
    "Table grid or header bands cannot be resolved safely.",
    detail_fields={"native_editing": DetailText | None},
)
TABLE003 = _rule(
    "TABLE003",
    WARNING,
    "Declared data table has no semantic headers.",
    detail_fields={"table": DetailText | None, "rows": int},
)
LANG001 = _rule("LANG001", WARNING, "Target has no established language declaration.")
LANG002 = _rule(
    "LANG002",
    WARNING,
    "Effective target language cannot be resolved safely.",
    detail_fields={"native_editing": DetailText},
)
REF001 = _rule(
    "REF001",
    ERROR,
    "Reference destination is missing.",
    detail_fields={
        "target": DetailText | None,
        "target_kind": DetailText | None,
        "native_editing": DetailText,
    },
)
REF002 = _rule(
    "REF002",
    ERROR,
    "Reference destination is ambiguous.",
    detail_fields={
        "target": DetailText | None,
        "target_kind": DetailText | None,
        "native_editing": DetailText,
    },
)
REF003 = _rule("REF003", ERROR, "Named range has inconsistent endpoints or identity.")
REF004 = _rule(
    "REF004",
    WARNING,
    "Reference destination requires native scope review.",
    detail_fields={
        "target": DetailText | None,
        "target_kind": DetailText | None,
        "native_editing": DetailText,
    },
)
NOTE002 = _rule("NOTE002", ERROR, "Note reference class differs from its destination.")
NOTE003 = _rule("NOTE003", ERROR, "Note anchor, citation or body relationship is incomplete.")
NOTE004 = _rule("NOTE004", ERROR, "Note identity is duplicated.")
LINK001 = _rule(
    "LINK001",
    WARNING,
    "Visible URL or email address is not a hyperlink.",
    detail_fields={"text": DetailText | None},
)
STYLE002 = _rule(
    "STYLE002",
    INFO,
    "Empty paragraphs may be visual spacers.",
    detail_fields={"count": int, "with_break_semantics": int, "styles": DetailList},
)
STYLE003 = _rule("STYLE003", ERROR, "Blinking text styling is declared.")

SHEET001 = _rule(
    "SHEET001", ERROR, "Sheet has no name.", detail_fields={"sheet": DetailText | None}
)
SHEET002 = _rule(
    "SHEET002", WARNING, "Sheet keeps its default name.", detail_fields={"sheet": DetailText | None}
)
TABLE004 = _rule(
    "TABLE004",
    WARNING,
    "Data sheet marks no header rows.",
    detail_fields={"sheet": DetailText | None},
)
TABLE005 = _rule(
    "TABLE005",
    WARNING,
    "Data sheet merges cells.",
    detail_fields={"sheet": DetailText | None, "merged_cells": int},
)
LINK002 = _rule(
    "LINK002",
    WARNING,
    "Hyperlink text is a raw address.",
    detail_fields={"text": DetailText | None},
)
SHEET003 = _rule(
    "SHEET003",
    WARNING,
    "Empty sheet follows the last sheet with content.",
    detail_fields={"sheet": DetailText | None},
)

PAGE001 = _rule("PAGE001", ERROR, "The document contains no pages.")
PAGE002 = _rule("PAGE002", ERROR, "Page has no unique nonempty name.")
PAGE003 = _rule(
    "PAGE003",
    WARNING,
    "Page has no accessible title.",
    detail_fields={"page": DetailText | None, "shape_identities": DetailList},
)
GRAPHIC002 = _rule(
    "GRAPHIC002",
    WARNING,
    "Nontext shape needs a meaning/decorative-content decision.",
    detail_fields={
        "page": DetailText | None,
        "shape_identities": DetailList,
        "shape": DetailText | None,
    },
)
PAGE004 = _rule(
    "PAGE004",
    ERROR,
    "Navigation order is incomplete or ambiguous.",
    detail_fields={
        "page": DetailText | None,
        "shape_identities": DetailList,
        "shape": DetailText | None,
    },
)
PAGE005 = _rule(
    "PAGE005",
    WARNING,
    "Page has no explicit navigation order.",
    detail_fields={
        "page": DetailText | None,
        "shape_identities": DetailList,
        "shape": DetailText | None,
    },
)
LINK003 = _rule("LINK003", ERROR, "Hyperlink has no readable purpose.")


MATH001 = _rule(
    "MATH001",
    ERROR,
    "Formula content must be a native MathML root; flat office wrappers are unsupported.",
)
MATH002 = _rule("MATH002", ERROR, "The mathematical expression is empty.")
MATH003 = _rule("MATH003", ERROR, "Formula has no spoken alternative.")
MATH004 = _rule("MATH004", WARNING, "Formula references external content requiring review.")

CHART001 = _rule("CHART001", ERROR, "Chart body does not contain exactly one chart.")
CHART002 = _rule("CHART002", ERROR, "The chart declares no data series.")
CHART003 = _rule("CHART003", WARNING, "Chart has no identifying title.")
CHART004 = _rule("CHART004", ERROR, "Chart has no supplied document description.")
CHART005 = _rule("CHART005", ERROR, "Local chart range does not match its declared data grid.")
CHART006 = _rule(
    "CHART006", WARNING, "Chart refers to an external data provider; it was not fetched."
)
CHART007 = _rule(
    "CHART007", WARNING, "Chart data range cannot be resolved against its local cache."
)
CHART008 = _rule("CHART008", WARNING, "Chart has no readable cached category or series labels.")
CHART009 = _rule(
    "CHART009", WARNING, "A multidimensional series range needs ordering/label review."
)
CHART010 = _rule(
    "CHART010", WARNING, "Cached categories and series values have different logical lengths."
)
CHART011 = _rule(
    "CHART011", WARNING, "Series includes nonblank cells without a numeric or temporal value type."
)

IMAGE001 = _rule(
    "IMAGE001", WARNING, "SVG declares active or external content requiring native review."
)
IMAGE002 = _rule("IMAGE002", ERROR, "Image payload is malformed or unsafe to inspect.")
IMAGE003 = _rule("IMAGE003", ERROR, "Image body does not contain one supported graphic frame.")
IMAGE004 = _rule("IMAGE004", ERROR, "Image frame has no image payload.")
IMAGE005 = _rule("IMAGE005", WARNING, "Image resource is external, unavailable or not embedded.")

DATABASE001 = _rule("DATABASE001", ERROR, "Document does not contain exactly one database body.")
DATABASE002 = _rule("DATABASE002", ERROR, "Database declares no connection resource.")
DATABASE003 = _rule("DATABASE003", ERROR, "Embedded database connection has no embedded storage.")
DATABASE004 = _rule("DATABASE004", WARNING, "Database has external connection declarations.")
DATABASE005 = _rule(
    "DATABASE005", WARNING, "Database stores a login identity; its value is not reported."
)
DATABASE006 = _rule(
    "DATABASE006", WARNING, "Connection declares credentials; values are not reported."
)
DATABASE007 = _rule(
    "DATABASE007", WARNING, "Database stores authentication settings; values are not reported."
)
DATABASE008 = _rule("DATABASE008", WARNING, "Database object target is ambiguous.")
DATABASE009 = _rule("DATABASE009", WARNING, "Database object has no description.")
DATABASE010 = _rule(
    "DATABASE010", WARNING, "Database has executable scripts requiring offline review."
)
DATABASE011 = _rule(
    "DATABASE011",
    INFO,
    "Queries, forms or reports require native semantic review.",
    detail_fields={"query_count": int},
)
DATABASE012 = _rule(
    "DATABASE012",
    INFO,
    "Forms and reports require native review; their payloads remain opaque.",
    detail_fields={"component_count": int},
)

PDF001 = _rule("PDF001", ERROR, "PDF cannot be opened or strictly inspected.")
PDF002 = _rule("PDF002", ERROR, "Document title is missing.")
PDF003 = _rule("PDF003", ERROR, "Catalog language is missing.")
PDF004 = _rule("PDF004", ERROR, "PDF is not marked as tagged.")
PDF005 = _rule("PDF005", ERROR, "Structure tree root is absent or empty.")
PDF006 = _rule("PDF006", WARNING, "Viewer preferences do not display the title.")
PDF007 = _rule("PDF007", ERROR, "XMP metadata does not declare PDF/UA part 1.")
PDF008 = _rule(
    "PDF008",
    ERROR,
    "A Figure structure element has no alternative text.",
    detail_fields={"figure_xrefs": DetailList, "missing_alt_xrefs": DetailList},
)
PDF009 = _rule("PDF009", INFO, "No numbered heading structure elements were found.")
PDF010 = _rule("PDF010", ERROR, "PDF has no pages.")
PDF011 = _rule(
    "PDF011", ERROR, "No extractable text or inspected described graphical content was found."
)
PDF012 = _rule(
    "PDF012",
    ERROR,
    "A custom structure role does not resolve to a standard role.",
    detail_fields={"unmapped_structure_types": DetailList},
)
PDF013 = _rule(
    "PDF013",
    ERROR,
    "The first numbered PDF heading starts below level one.",
    detail_fields={"level": int},
)
PDF014 = _rule(
    "PDF014", ERROR, "List structure is malformed.", detail_fields={"problems": DetailList}
)
PDF015 = _rule(
    "PDF015", ERROR, "Table structure is malformed.", detail_fields={"problems": DetailList}
)
PDF016 = _rule("PDF016", WARNING, "Table has no header cells.", detail_fields={"rows": int})
PDF017 = _rule(
    "PDF017",
    WARNING,
    "A link annotation is not represented by a Link element.",
    detail_fields={"count": int, "annotations": DetailList},
)
PDF018 = _rule(
    "PDF018",
    WARNING,
    "A Link structure element refers to no link annotation.",
    detail_fields={"count": int, "page_xrefs": DetailList},
)
PDF019 = _rule(
    "PDF019",
    ERROR,
    "A link annotation is referenced from another page.",
    detail_fields={"count": int, "annotations": DetailList},
)
PDF020 = _rule(
    "PDF020",
    ERROR,
    "A link has no alternate description.",
    detail_fields={"count": int, "annotations": DetailList},
)
PDF021 = _rule(
    "PDF021",
    ERROR,
    "Marked content in an inspected stream is not part of the structure tree.",
    detail_fields={"pages": DetailList},
)
PDF022 = _rule(
    "PDF022",
    WARNING,
    "A structure element refers to marked content its inspected stream does not have.",
    detail_fields={"count": int, "references": DetailList},
)
PDF023 = _rule(
    "PDF023",
    WARNING,
    "Marked content is referenced by more than one element.",
    detail_fields={"count": int, "mcids": DetailList},
)
PDF024 = _rule(
    "PDF024",
    ERROR,
    "Text is shown outside tagged content and artifacts.",
    detail_fields={"pages": DetailList},
)
PDF025 = _rule(
    "PDF025",
    ERROR,
    "Numbered PDF heading hierarchy skips a level.",
    detail_fields={"skips": DetailList},
)
PDFUA001 = _rule(
    "PDFUA001",
    ERROR,
    "veraPDF reports a failed PDF/UA-1 rule.",
    detail_fields={
        "specification": DetailText | None,
        "clause": DetailText | None,
        "test_number": DetailText | None,
        "failed_checks": int,
        "contexts": DetailList,
        "messages": DetailList,
    },
)

FIDELITY001 = _rule(
    "FIDELITY001", ERROR, "Page count differs.", detail_fields={"source": int, "candidate": int}
)
FIDELITY002 = _rule(
    "FIDELITY002", ERROR, "Page dimensions differ.", detail_fields={"pages": DetailList}
)
FIDELITY003 = _rule(
    "FIDELITY003",
    ERROR,
    "Document text differs.",
    detail_fields={"position": int, "source": DetailText, "candidate": DetailText},
)
FIDELITY004 = _rule(
    "FIDELITY004",
    ERROR,
    "A source link is missing or changed.",
    detail_fields={"missing": DetailList},
)
FIDELITY005 = _rule(
    "FIDELITY005",
    ERROR,
    "Rendered page differs beyond the tolerance.",
    detail_fields={"page": int, "changed_ratio": float, "diff_image": DetailText},
)
FIDELITY006 = _rule("FIDELITY006", INFO, "Links were added.", detail_fields={"added": DetailList})
FIDELITY007 = _rule(
    "FIDELITY007",
    ERROR,
    "A page is too large to render for comparison.",
    detail_fields={"pages": DetailList, "pixel_limit": int},
)


FIDELITY008 = _rule(
    "FIDELITY008",
    ERROR,
    "A URI destination cannot be established.",
    detail_fields={
        "artifact": Literal["source", "candidate"],
        "page": int | None,
        "problem": DetailText,
    },
)


GRAPHIC003 = _rule("GRAPHIC003", WARNING, "Graphic decorative role is unresolved or unsafe.")
GRAPHIC004 = _rule(
    "GRAPHIC004", WARNING, "Decorative graphic retains authored alternative metadata."
)


LIST001 = _rule("LIST001", ERROR, "List XML identity is duplicated.")
LIST002 = _rule("LIST002", ERROR, "List membership or nesting is structurally invalid.")
LIST003 = _rule("LIST003", ERROR, "A nested list must belong to a list item or header.")
LIST004 = _rule("LIST004", ERROR, "List continuation has an invalid boolean declaration.")
LIST005 = _rule("LIST005", ERROR, "List continuation participates in a counter cycle.")
LIST006 = _rule(
    "LIST006",
    ERROR,
    "List continuation target is missing or ambiguous.",
    detail_fields={"reference": DetailText | None},
)
LIST007 = _rule("LIST007", WARNING, "List continuation crosses a reading or counter domain.")
LIST008 = _rule("LIST008", WARNING, "List counter continuation requires native review.")
LIST009 = _rule(
    "LIST009",
    WARNING,
    "Paragraph resembles a manually simulated list.",
    detail_fields={"native_editing": DetailText},
)
