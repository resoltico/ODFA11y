# SPDX-License-Identifier: MPL-2.0
"""ODF XML namespace prefixes and qualified-name construction."""

lazy from lxml import etree

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "dc": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "chart": "urn:oasis:names:tc:opendocument:xmlns:chart:1.0",
    "db": "urn:oasis:names:tc:opendocument:xmlns:database:1.0",
    "form": "urn:oasis:names:tc:opendocument:xmlns:form:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
    "anim": "urn:oasis:names:tc:opendocument:xmlns:animation:1.0",
    "script": "urn:oasis:names:tc:opendocument:xmlns:script:1.0",
    "dr3d": "urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0",
    "math": "http://www.w3.org/1998/Math/MathML",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}


def is_office_element(element: etree._Element) -> bool:
    """Whether an element is in the ODF ``office`` namespace (a document root, not MathML).

    Returns
    -------
    bool
        True for elements such as ``office:document-content``; False for comments and others.

    """
    return isinstance(element.tag, str) and element.tag.startswith(f"{{{NS['office']}}}")


def qn(prefix: str, local: str) -> str:
    """Expand a namespace prefix and local name into a qualified XML name.

    Returns
    -------
    str
        The expanded XML namespace name.

    """
    return f"{{{NS[prefix]}}}{local}"


# Qualified XML names shared by document checks and edits.
CHART_CHART = qn("chart", "chart")
CHART_LABEL_CELL_ADDRESS = qn("chart", "label-cell-address")
CHART_VALUES_CELL_RANGE_ADDRESS = qn("chart", "values-cell-range-address")
CONFIG_NAMESPACE = "{urn:oasis:names:tc:opendocument:xmlns:config:1.0}"
DB_DATA_SOURCE_SETTING = qn("db", "data-source-setting")
DB_DATA_SOURCE_SETTING_NAME = qn("db", "data-source-setting-name")
DB_DATA_SOURCE_SETTING_TYPE = qn("db", "data-source-setting-type")
DB_DATA_SOURCE_SETTING_VALUE = qn("db", "data-source-setting-value")
DB_DESCRIPTION = qn("db", "description")
DB_NAME = qn("db", "name")
DB_USER_NAME = qn("db", "user-name")
DC_DESCRIPTION = qn("dc", "description")
DC_LANGUAGE = qn("dc", "language")
DC_TITLE = qn("dc", "title")
DR3D_SCENE = qn("dr3d", "scene")
DRAW_A = qn("draw", "a")
DRAW_APPLET = qn("draw", "applet")
DRAW_CONTOUR_PATH = qn("draw", "contour-path")
DRAW_CONTOUR_POLYGON = qn("draw", "contour-polygon")
DRAW_CONTROL = qn("draw", "control")
DRAW_DECORATIVE = qn("draw", "decorative")
DRAW_FRAME = qn("draw", "frame")
DRAW_G = qn("draw", "g")
DRAW_ID = qn("draw", "id")
DRAW_IMAGE = qn("draw", "image")
DRAW_NAME = qn("draw", "name")
DRAW_NAV_ORDER = qn("draw", "nav-order")
DRAW_OBJECT = qn("draw", "object")
DRAW_OBJECT_OLE = qn("draw", "object-ole")
DRAW_PAGE = qn("draw", "page")
DRAW_PAGE_THUMBNAIL = qn("draw", "page-thumbnail")
DRAW_STYLE_NAME = qn("draw", "style-name")
DRAW_TEXT_BOX = qn("draw", "text-box")
FORM_ = qn("form", "")
FORM_DATASOURCE = qn("form", "datasource")
FORM_FORM = qn("form", "form")
FORM_IMAGE_DATA = qn("form", "image-data")
FORM_NAME = qn("form", "name")
FORM_TITLE = qn("form", "title")
FO_BREAK_AFTER = qn("fo", "break-after")
FO_BREAK_BEFORE = qn("fo", "break-before")
FO_COLUMN_COUNT = qn("fo", "column-count")
FO_LINE_HEIGHT = qn("fo", "line-height")
FO_LINE_HEIGHT_AT_LEAST = qn("fo", "line-height-at-least")
FO_MARGIN_BOTTOM = qn("fo", "margin-bottom")
FO_MARGIN_TOP = qn("fo", "margin-top")
MANIFEST_FILE_ENTRY = qn("manifest", "file-entry")
MANIFEST_FULL_PATH = qn("manifest", "full-path")
MANIFEST_MANIFEST = qn("manifest", "manifest")
MANIFEST_MEDIA_TYPE = qn("manifest", "media-type")
MANIFEST_VERSION = qn("manifest", "version")
MATH_CSYMBOL = qn("math", "csymbol")
MATH_MATH = qn("math", "math")
MATH_MGLYPH = qn("math", "mglyph")
MATH_MS = qn("math", "ms")
MIMETYPE_MEMBER = "mimetype"
OFFICE_ANNOTATION = qn("office", "annotation")
OFFICE_AUTOMATIC_STYLES = qn("office", "automatic-styles")
OFFICE_BINARY_DATA = qn("office", "binary-data")
OFFICE_BODY = qn("office", "body")
OFFICE_DDE_APPLICATION = qn("office", "dde-application")
OFFICE_DDE_SOURCE = qn("office", "dde-source")
OFFICE_DOCUMENT = qn("office", "document")
OFFICE_DOCUMENT_CONTENT = qn("office", "document-content")
OFFICE_DOCUMENT_META = qn("office", "document-meta")
OFFICE_DOCUMENT_STYLES = qn("office", "document-styles")
OFFICE_EVENT_LISTENERS = qn("office", "event-listeners")
OFFICE_META = qn("office", "meta")
OFFICE_MIMETYPE = qn("office", "mimetype")
OFFICE_NAME = qn("office", "name")
OFFICE_SPREADSHEET = qn("office", "spreadsheet")
OFFICE_STYLES = qn("office", "styles")
OFFICE_TITLE = qn("office", "title")
OFFICE_VALUE_TYPE = qn("office", "value-type")
OFFICE_VERSION = qn("office", "version")
PDFUA_PART = "{http://www.aiim.org/pdfua/ns/id/}part"
PRESENTATION_ACTION = qn("presentation", "action")
PRESENTATION_EVENT_LISTENER = qn("presentation", "event-listener")
PRESENTATION_PLACEHOLDER = qn("presentation", "placeholder")
STYLE_BASE_CELL_ADDRESS = qn("style", "base-cell-address")
STYLE_COLUMN = qn("style", "column")
STYLE_CONDITION = qn("style", "condition")
STYLE_CONTEXTUAL_SPACING = qn("style", "contextual-spacing")
STYLE_DEFAULT_STYLE = qn("style", "default-style")
STYLE_FAMILY = qn("style", "family")
STYLE_GRAPHIC_PROPERTIES = qn("style", "graphic-properties")
STYLE_MASTER_PAGE_NAME = qn("style", "master-page-name")
STYLE_NAME = qn("style", "name")
STYLE_PAGE_NUMBER = qn("style", "page-number")
STYLE_PARAGRAPH_PROPERTIES = qn("style", "paragraph-properties")
STYLE_PARENT_STYLE_NAME = qn("style", "parent-style-name")
STYLE_STYLE = qn("style", "style")
STYLE_TEXT_PROPERTIES = qn("style", "text-properties")
SVG_DESC = qn("svg", "desc")
SVG_TITLE = qn("svg", "title")
TABLE_BASE_CELL_ADDRESS = qn("table", "base-cell-address")
TABLE_CELL_RANGE_ADDRESS = qn("table", "cell-range-address")
TABLE_CELL_RANGE_SOURCE = qn("table", "cell-range-source")
TABLE_CONDITION = qn("table", "condition")
TABLE_COVERED_TABLE_CELL = qn("table", "covered-table-cell")
TABLE_DATABASE_NAME = qn("table", "database-name")
TABLE_EXPRESSION = qn("table", "expression")
TABLE_FORMULA = qn("table", "formula")
TABLE_NAME = qn("table", "name")
TABLE_NAMED_EXPRESSION = qn("table", "named-expression")
TABLE_NAMED_RANGE = qn("table", "named-range")
TABLE_NUMBER_ROWS_REPEATED = qn("table", "number-rows-repeated")
TABLE_SOURCE_CELL_RANGE = qn("table", "source-cell-range")
TABLE_SOURCE_SERVICE = qn("table", "source-service")
TABLE_STYLE_NAME = qn("table", "style-name")
TABLE_TABLE = qn("table", "table")
TABLE_TABLE_CELL = qn("table", "table-cell")
TABLE_TABLE_COLUMN = qn("table", "table-column")
TABLE_TABLE_HEADER_COLUMNS = qn("table", "table-header-columns")
TABLE_TABLE_HEADER_ROWS = qn("table", "table-header-rows")
TABLE_TABLE_ROW = qn("table", "table-row")
TEXT_A = qn("text", "a")
TEXT_ANCHOR_TYPE = qn("text", "anchor-type")
TEXT_C = qn("text", "c")
TEXT_CHANGE = qn("text", "change")
TEXT_CHANGE_END = qn("text", "change-end")
TEXT_CHANGE_ID = qn("text", "change-id")
TEXT_CHANGE_START = qn("text", "change-start")
TEXT_CONDITION = qn("text", "condition")
TEXT_CONDITIONAL_TEXT = qn("text", "conditional-text")
TEXT_CONTINUE_LIST = qn("text", "continue-list")
TEXT_CONTINUE_NUMBERING = qn("text", "continue-numbering")
TEXT_CURRENT_VALUE = qn("text", "current-value")
TEXT_DATABASE_NAME = qn("text", "database-name")
TEXT_DDE_CONNECTION_DECL = qn("text", "dde-connection-decl")
TEXT_DELETION = qn("text", "deletion")
TEXT_DISPLAY = qn("text", "display")
TEXT_FILE_NAME = qn("text", "file-name")
TEXT_FORMULA = qn("text", "formula")
TEXT_H = qn("text", "h")
TEXT_HIDDEN_PARAGRAPH = qn("text", "hidden-paragraph")
TEXT_HIDDEN_TEXT = qn("text", "hidden-text")
TEXT_ID = qn("text", "id")
TEXT_IS_HIDDEN = qn("text", "is-hidden")
TEXT_LIST = qn("text", "list")
TEXT_LIST_HEADER = qn("text", "list-header")
TEXT_LIST_ITEM = qn("text", "list-item")
TEXT_NAME = qn("text", "name")
TEXT_NOTE = qn("text", "note")
TEXT_NOTE_BODY = qn("text", "note-body")
TEXT_NOTE_CITATION = qn("text", "note-citation")
TEXT_NOTE_CLASS = qn("text", "note-class")
TEXT_OUTLINE_LEVEL = qn("text", "outline-level")
TEXT_P = qn("text", "p")
TEXT_REF_NAME = qn("text", "ref-name")
TEXT_S = qn("text", "s")
TEXT_SECTION = qn("text", "section")
TEXT_SPAN = qn("text", "span")
TEXT_STYLE_NAME = qn("text", "style-name")
TEXT_TRACKED_CHANGES = qn("text", "tracked-changes")
XLINK_HREF = qn("xlink", "href")
XLINK_TYPE = qn("xlink", "type")
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

SVG_WIDTH = qn("svg", "width")

FO_KEEP_WITH_NEXT = qn("fo", "keep-with-next")
FO_FONT_WEIGHT = qn("fo", "font-weight")
DRAW_FILL_COLOR = qn("draw", "fill-color")
