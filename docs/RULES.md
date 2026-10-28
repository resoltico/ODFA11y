# Rule reference

Rules define each finding's identity, severity, category and possible decision kinds.
Findings reference these rules; open decisions carry the human questions.
The [registry](../src/odfa11y/report/rules.py) is authoritative.

## Registered rules

| ID | Severity | Finding | Decision kinds |
| --- | --- | --- | --- |
| `BASE001` | Error | Database body, connection or embedded storage is missing. |  |
| `BASE002` | Warning | Database has external connection declarations. |  |
| `BASE003` | Warning | Database stores authentication information requiring privacy review. |  |
| `BASE004` | Warning | Database object description is missing or ambiguous. | `database.description` |
| `BASE005` | Warning | Database has executable scripts requiring offline review. |  |
| `BASE006` | Info | Queries, forms or reports require native semantic review. |  |
| `CHART001` | Error | Chart body or data series is missing or ambiguous. |  |
| `CHART002` | Warning | Chart has no identifying title. | `document.metadata` |
| `CHART003` | Error | Chart has no supplied document description. | `document.metadata` |
| `CHART004` | Error | Local chart range does not match its declared data grid. |  |
| `CHART005` | Warning | Chart data provider or range cannot be verified locally. |  |
| `CHART006` | Warning | Chart labels or data ordering need review. |  |
| `FID001` | Error | Page count differs. |  |
| `FID002` | Error | Page dimensions differ. |  |
| `FID003` | Error | Document text differs. |  |
| `FID004` | Error | A source link is missing or changed. |  |
| `FID005` | Error | Rendered page differs beyond the tolerance. |  |
| `FID006` | Info | Links were added. |  |
| `FID007` | Error | A page is too large to render for comparison. |  |
| `GRAPHIC001` | Warning | Graphic decorative role is unresolved or unsafe. |  |
| `GRAPHIC002` | Warning | Decorative graphic retains authored alternative metadata. |  |
| `GRAPHIC003` | Error | Graphic has neither accessible title nor description. | `graphic.alternative` |
| `GRAPHIC005` | Warning | Nontext shape needs a meaning/decorative-content decision. | `graphic.alternative` |
| `HEADING001` | Error | Heading has no valid outline level. | `heading.level` |
| `HEADING002` | Error | Heading hierarchy starts too deep or skips a level. | `heading.level` |
| `HEADING003` | Warning | Heading text resembles manually typed numbering. |  |
| `HEADING004` | Info | No structural headings were found. |  |
| `HIDDEN001` | Warning | Hidden or conditional content requires visibility review. |  |
| `IMAGE001` | Error | Image body does not contain one supported graphic frame. |  |
| `IMAGE003` | Warning | Image resource is external, unavailable or not embedded. |  |
| `IMAGE004` | Error | Image payload is malformed or unsafe to inspect. |  |
| `IMAGE005` | Warning | SVG declares active or external content requiring native review. |  |
| `LAYOUT001` | Info | Empty paragraphs may be visual spacers. | `text.remove_spacers` |
| `LINK001` | Warning | Visible URL or email address is not a hyperlink. | `text.linkify_addresses` |
| `LINK002` | Warning | Hyperlink text is a raw address. |  |
| `LINK003` | Error | Hyperlink has no readable purpose. | `link.description` |
| `MATH001` | Error | Native mathematical expression is missing or unsupported. |  |
| `MATH002` | Error | Formula has no spoken alternative. | `formula.alternative` |
| `MATH003` | Warning | Formula references external content requiring review. |  |
| `META001` | Error | Document title metadata is missing. | `document.metadata` |
| `META002` | Error | Document language is not declared. | `document.metadata` |
| `META003` | Warning | Metadata and default style languages disagree. | `document.metadata` |
| `META004` | Warning | Document language syntax or default-style target is unresolved. |  |
| `NATIVE001` | Warning | Native resource declarations are unresolved or unestablished. |  |
| `NATIVE002` | Warning | Pipeline export cannot preserve filename/path fields. |  |
| `NOTE001` | Warning | Notes or annotations need relationship and reading-order review. |  |
| `ODF001` | Error | Package members declare different ODF versions. | `document.odf_version` |
| `ODF002` | Error | Manifest root file-entry '/' is missing. |  |
| `ODF003` | Error | Manifest root file-entry version differs from the document version. | `document.odf_version` |
| `ODF004` | Error | Manifest root media type differs from the document's. |  |
| `ODF005` | Error | The media type is not an OpenDocument document type. |  |
| `ODF006` | Error | The document body does not match its media type. |  |
| `ODF007` | Warning | The file extension does not match the media type. |  |
| `ODF008` | Warning | The document kind is deprecated. |  |
| `ODF009` | Info | No semantic audit exists for this document family. |  |
| `ODF010` | Error | A flat XML document's root is not office:document. |  |
| `ODF011` | Error | A package's content root is not office:document-content. |  |
| `PAGE001` | Error | Pages are missing, unnamed or ambiguously named. |  |
| `PAGE002` | Warning | Page has no accessible title. | `page.metadata` |
| `PAGE003` | Error | Navigation order is incomplete or ambiguous. | `page.navigation` |
| `PAGE004` | Warning | Page has no explicit navigation order. | `page.navigation` |
| `PDF000` | Error | PDF cannot be opened or strictly inspected. |  |
| `PDF001` | Error | Document title is missing. |  |
| `PDF002` | Error | Catalog language is missing. |  |
| `PDF003` | Error | PDF is not marked as tagged. |  |
| `PDF004` | Error | Structure tree root is absent or empty. |  |
| `PDF005` | Warning | Viewer preferences do not display the title. |  |
| `PDF006` | Error | XMP metadata does not declare PDF/UA part 1. |  |
| `PDF007` | Error | A Figure structure element has no alternative text. |  |
| `PDF008` | Info | No numbered heading structure elements were found. |  |
| `PDF009` | Error | PDF has no pages. |  |
| `PDF010` | Error | No extractable text or inspected described graphical content was found. |  |
| `PDF011` | Error | A custom structure role does not resolve to a standard role. |  |
| `PDF012` | Error | Heading structure starts too deep or skips a level. |  |
| `PDF013` | Error | List structure is malformed. |  |
| `PDF014` | Error | Table structure is malformed. |  |
| `PDF015` | Warning | Table has no header cells. |  |
| `PDF016` | Warning | A link annotation is not represented by a Link element. |  |
| `PDF017` | Warning | A Link structure element refers to no link annotation. |  |
| `PDF018` | Error | A link annotation is referenced from another page. |  |
| `PDF019` | Error | A link has no alternate description. |  |
| `PDF020` | Error | Marked content in an inspected stream is not part of the structure tree. |  |
| `PDF021` | Warning | A structure element refers to marked content its inspected stream does not have. |  |
| `PDF022` | Warning | Marked content is referenced by more than one element. |  |
| `PDF023` | Error | Text is shown outside tagged content and artifacts. |  |
| `PKG000` | Error | Source is not a readable ODF package or flat XML document. |  |
| `PKG001` | Warning | The document does not declare its media type. |  |
| `PKG002` | Warning | An optional package member is missing. |  |
| `PKG003` | Error | mimetype is not the first ZIP member. |  |
| `PKG004` | Error | mimetype is compressed. |  |
| `PKG005` | Error | A member the document needs is missing. |  |
| `PKG006` | Error | ZIP member names are duplicated. |  |
| `PKG007` | Error | A ZIP member name is absolute or escapes its directory. |  |
| `PKG008` | Warning | Declared signatures are unverified. |  |
| `PKG009` | Error | Manifest encryption prevents complete inspection. |  |
| `REVISION001` | Warning | Tracked revision scope requires review. |  |
| `SCHEMA001` | Warning | A member does not validate against the ODF schema. |  |
| `SCHEMA002` | Info | No ODF schema is bundled for the declared version. |  |
| `SHEET001` | Error | Sheet has no name. |  |
| `SHEET002` | Warning | Sheet keeps its default name. | `sheet.name` |
| `SHEET007` | Warning | Empty sheet follows the last sheet with content. |  |
| `STYLE001` | Warning | Paragraph style scope or properties are unresolved. |  |
| `STYLE002` | Error | Blinking text styling is declared. |  |
| `TABLE001` | Warning | Merged table cells need header-relationship review. |  |
| `TABLE002` | Error | Table grid or header bands cannot be resolved safely. |  |
| `TABLE003` | Warning | Data-like table has no semantic headers. | `table.headers` |
| `TABLE004` | Warning | Data sheet marks no header rows. |  |
| `TABLE005` | Warning | Data sheet merges cells. |  |
| `VERA000` | Warning | The requested veraPDF validator is unavailable. |  |
| `VERA001` | Error | veraPDF reports a failed PDF/UA-1 rule. |  |
| `XML001` | Error | A required XML member cannot be parsed. |  |

## Reading findings

`SCHEMA001` is a warning because pristine LibreOffice output often fails the strict ODF
schema (for example in `styles.xml`); the schema matters most as a *regression* gate,
which `remediate` enforces when a bundled schema is available: it refuses a result with
a detected violation the source did not already have. Source link, table, heading-numbering and spacer findings use heuristics; inspect the
source in context. Graphics need supplied titles or descriptions, and table headers need an unambiguous
reviewed table target with explicit leading row or column counts; unnamed ordinal targets
require their fingerprint. `LAYOUT001` is observational: [spacer
removal](ACCESSIBILITY.md#spacer-removal) is explicit and preserves protected structures.
The `SHEET` findings are structural: a *default name* is a name of the form `Sheet` and
digits (other languages' defaults are not recognised); a *data sheet* is one whose first row
with text holds at least two short labels and which has another row with text, and only such
sheets are checked for header rows (`table:table-header-rows`, which Calc writes for rows
repeated on every printed page) and merged cells. `GRAPHIC003` covers eligible frames and
vector shapes, including pictures, charts and embedded objects; `LINK002` flags raw-address labels without a native `office:title` description;
`SHEET007` flags empty sheets after the last one with text or graphics (the first sheet is
always kept); `HIDDEN001` reports counts, as hidden content is sometimes intended. Header
rows, merged cells, visible link text and hidden content need a person's decision in Calc.
Sheet names, eligible graphic alternatives/roles and native link descriptions have explicit
typed decisions. `LINK003` reports links without readable source purpose; a supplied
`office:title` can establish purpose without rewriting labels or target names.
`VERA001` appears once per failed veraPDF rule and keeps the standard's clause and test
number in its details. `PDF` findings are a fast smoke test, not PDF/UA validation.

## Locations

A finding's `location` is logical, so the same document audits to the same locations as a
package (`.odt`) and as flat XML (`.fodt`). It has a `path` and an optional `member`, the
stored package member, which is set only where that physical detail helps (package-level
defects such as `ODF004` or `PKG004`). A finding with no location applies to the whole
file; an audit reports no location at all for a source it cannot open.

```text
path     = part ( "/" segment )*
part     = "content" | "styles" | "meta" | "settings" | "manifest" | "package" | "document"
segment  = domain_name [ "[" ref "]" ]
ref      = "name=" percent_encoded_name | "id=" percent_encoded_identity | N
```


`domain_name` identifies the audited domain object or field: for example `heading`,
`paragraph`, `table`, `frame`, `page`, `shape`, `formula`, `chart`, `chart-range`, `query`,
`query-collection`, `column`, `title`, `description`, `language` or `mimetype`. Nested Base
objects retain parent segments, such as
`content/query-collection[name=Fruit]/query[name=Totals]/column[name=Count]`.
Named and XML-identity values percent-encode reserved delimiters; consumers must not
split decoded names as path syntax. `N` counts from 1 in document order, separately for each kind: `heading[2]` is the second
`text:h`, `paragraph[3]` the third `text:p` (headings are not paragraphs here). `ref` is the
element's percent-encoded declared name (`table[name=Data]`, `frame[name=Logo]`) or, when it has none, its
index among tables or graphics (`table[2]`). `meta/title` and `meta/language` name the
missing or conflicting metadata field. `styles` covers style definitions wherever they are
stored, `package/mimetype` is the ZIP `mimetype` member, and `document` is a flat file or
a schema or parse defect in one. The text report prints `path` followed by the member in
parentheses, for example `manifest (META-INF/manifest.xml)`.
