# Rule reference

Rules define each finding's identity, severity, category and possible decision kinds.
Findings reference these rules; open decisions carry the human questions.
The [registry](../src/odfa11y/rules/registry.py) is authoritative.

## Registered rules

| ID | Severity | Finding | Decision kinds |
| --- | --- | --- | --- |
| `CHART001` | Error | Chart body does not contain exactly one chart. |  |
| `CHART002` | Error | The chart declares no data series. |  |
| `CHART003` | Warning | Chart has no identifying title. | `document.metadata` |
| `CHART004` | Error | Chart has no supplied document description. | `document.metadata` |
| `CHART005` | Error | Local chart range does not match its declared data grid. |  |
| `CHART006` | Warning | Chart refers to an external data provider; it was not fetched. |  |
| `CHART007` | Warning | Chart data range cannot be resolved against its local cache. |  |
| `CHART008` | Warning | Chart has no readable cached category or series labels. |  |
| `CHART009` | Warning | A multidimensional series range needs ordering/label review. |  |
| `CHART010` | Warning | Cached categories and series values have different logical lengths. |  |
| `CHART011` | Warning | Series includes nonblank cells without a numeric or temporal value type. |  |
| `DATABASE001` | Error | Document does not contain exactly one database body. |  |
| `DATABASE002` | Error | Database declares no connection resource. |  |
| `DATABASE003` | Error | Embedded database connection has no embedded storage. |  |
| `DATABASE004` | Warning | Database has external connection declarations. |  |
| `DATABASE005` | Warning | Database stores a login identity; its value is not reported. |  |
| `DATABASE006` | Warning | Connection declares credentials; values are not reported. |  |
| `DATABASE007` | Warning | Database stores authentication settings; values are not reported. |  |
| `DATABASE008` | Warning | Database object target is ambiguous. |  |
| `DATABASE009` | Warning | Database object has no description. | `database.description` |
| `DATABASE010` | Warning | Database has executable scripts requiring offline review. |  |
| `DATABASE011` | Info | Queries, forms or reports require native semantic review. |  |
| `DATABASE012` | Info | Forms and reports require native review; their payloads remain opaque. |  |
| `FIDELITY001` | Error | Page count differs. |  |
| `FIDELITY002` | Error | Page dimensions differ. |  |
| `FIDELITY003` | Error | Document text differs. |  |
| `FIDELITY004` | Error | A source link is missing or changed. |  |
| `FIDELITY005` | Error | Rendered page differs beyond the tolerance. |  |
| `FIDELITY006` | Info | Links were added. |  |
| `FIDELITY007` | Error | A page is too large to render for comparison. |  |
| `GRAPHIC001` | Error | Graphic has neither accessible title nor description. | `graphic.alternative` |
| `GRAPHIC002` | Warning | Nontext shape needs a meaning/decorative-content decision. | `graphic.alternative` |
| `GRAPHIC003` | Warning | Graphic decorative role is unresolved or unsafe. |  |
| `GRAPHIC004` | Warning | Decorative graphic retains authored alternative metadata. |  |
| `HEADING001` | Error | Heading has no valid outline level. | `heading.level` |
| `HEADING002` | Error | The first heading starts below level one. | `heading.level` |
| `HEADING003` | Error | Heading hierarchy skips an outline level. | `heading.level` |
| `HEADING004` | Warning | Heading text resembles manually typed numbering. |  |
| `HEADING005` | Info | No structural headings were found. |  |
| `IMAGE001` | Warning | SVG declares active or external content requiring native review. |  |
| `IMAGE002` | Error | Image payload is malformed or unsafe to inspect. |  |
| `IMAGE003` | Error | Image body does not contain one supported graphic frame. |  |
| `IMAGE004` | Error | Image frame has no image payload. |  |
| `IMAGE005` | Warning | Image resource is external, unavailable or not embedded. |  |
| `LANG001` | Warning | Target has no established language declaration. | `language.target` |
| `LANG002` | Warning | Effective target language cannot be resolved safely. |  |
| `LINK001` | Warning | Visible URL or email address is not a hyperlink. | `text.linkify_addresses` |
| `LINK002` | Warning | Hyperlink text is a raw address. |  |
| `LINK003` | Error | Hyperlink has no readable purpose. | `link.description` |
| `LIST001` | Error | List XML identity is duplicated. |  |
| `LIST002` | Error | List membership or nesting is structurally invalid. |  |
| `LIST003` | Error | A nested list must belong to a list item or header. |  |
| `LIST004` | Error | List continuation has an invalid boolean declaration. |  |
| `LIST005` | Error | List continuation participates in a counter cycle. |  |
| `LIST006` | Error | List continuation target is missing or ambiguous. |  |
| `LIST007` | Warning | List continuation crosses a reading or counter domain. |  |
| `LIST008` | Warning | List counter continuation requires native review. |  |
| `LIST009` | Warning | Paragraph resembles a manually simulated list. |  |
| `MATH001` | Error | Formula content must be a native MathML root; flat office wrappers are unsupported. |  |
| `MATH002` | Error | The mathematical expression is empty. |  |
| `MATH003` | Error | Formula has no spoken alternative. | `formula.alternative` |
| `MATH004` | Warning | Formula references external content requiring review. |  |
| `META001` | Error | Document title metadata is missing. | `document.metadata` |
| `META002` | Error | Document language is not declared. | `document.metadata` |
| `META003` | Warning | Metadata and default style languages disagree. | `document.metadata` |
| `META004` | Warning | Document language syntax or default-style target is unresolved. |  |
| `NATIVE001` | Warning | Native resource declarations are unresolved or unestablished. |  |
| `NATIVE002` | Warning | Pipeline export cannot preserve filename/path fields. |  |
| `NOTE001` | Warning | Notes or annotations need relationship and reading-order review. |  |
| `NOTE002` | Error | Note reference class differs from its destination. |  |
| `NOTE003` | Error | Note anchor, citation or body relationship is incomplete. |  |
| `NOTE004` | Error | Note identity is duplicated. |  |
| `ODF001` | Error | Package members declare different ODF versions. | `document.odf_version` |
| `ODF002` | Error | Manifest root file-entry '/' is missing. |  |
| `ODF003` | Error | Manifest version differs from the document version. | `document.odf_version` |
| `ODF004` | Error | Manifest root file-entry version differs from the document version. | `document.odf_version` |
| `ODF005` | Error | Manifest root media type differs from the document's. |  |
| `ODF006` | Error | The media type is not an OpenDocument document type. |  |
| `ODF007` | Error | The document body does not match its media type. |  |
| `ODF008` | Warning | The file extension does not match the media type. |  |
| `ODF009` | Warning | The document kind is deprecated. |  |
| `ODF010` | Info | No semantic audit exists for this document family. |  |
| `ODF011` | Error | A flat XML document's root is not office:document. |  |
| `ODF012` | Error | A package's content root is not office:document-content. |  |
| `ORDER001` | Warning | Visibility declarations are incomplete or contradictory. |  |
| `ORDER002` | Warning | Declared layout requires native reading-order review. |  |
| `ORDER003` | Warning | Hidden or conditional content requires visibility review. |  |
| `PAGE001` | Error | The document contains no pages. |  |
| `PAGE002` | Error | Page has no unique nonempty name. |  |
| `PAGE003` | Warning | Page has no accessible title. | `page.metadata` |
| `PAGE004` | Error | Navigation order is incomplete or ambiguous. | `page.navigation` |
| `PAGE005` | Warning | Page has no explicit navigation order. | `page.navigation` |
| `PDF001` | Error | PDF cannot be opened or strictly inspected. |  |
| `PDF002` | Error | Document title is missing. |  |
| `PDF003` | Error | Catalog language is missing. |  |
| `PDF004` | Error | PDF is not marked as tagged. |  |
| `PDF005` | Error | Structure tree root is absent or empty. |  |
| `PDF006` | Warning | Viewer preferences do not display the title. |  |
| `PDF007` | Error | XMP metadata does not declare PDF/UA part 1. |  |
| `PDF008` | Error | A Figure structure element has no alternative text. |  |
| `PDF009` | Info | No numbered heading structure elements were found. |  |
| `PDF010` | Error | PDF has no pages. |  |
| `PDF011` | Error | No extractable text or inspected described graphical content was found. |  |
| `PDF012` | Error | A custom structure role does not resolve to a standard role. |  |
| `PDF013` | Error | Heading structure starts too deep or skips a level. |  |
| `PDF014` | Error | List structure is malformed. |  |
| `PDF015` | Error | Table structure is malformed. |  |
| `PDF016` | Warning | Table has no header cells. |  |
| `PDF017` | Warning | A link annotation is not represented by a Link element. |  |
| `PDF018` | Warning | A Link structure element refers to no link annotation. |  |
| `PDF019` | Error | A link annotation is referenced from another page. |  |
| `PDF020` | Error | A link has no alternate description. |  |
| `PDF021` | Error | Marked content in an inspected stream is not part of the structure tree. |  |
| `PDF022` | Warning | A structure element refers to marked content its inspected stream does not have. |  |
| `PDF023` | Warning | Marked content is referenced by more than one element. |  |
| `PDF024` | Error | Text is shown outside tagged content and artifacts. |  |
| `PDFUA001` | Error | veraPDF reports a failed PDF/UA-1 rule. |  |
| `PKG001` | Error | Source is not a readable ODF package or flat XML document. |  |
| `PKG002` | Warning | The document has no office:mimetype attribute. |  |
| `PKG003` | Warning | Package has no mimetype member; tools cannot recognise its type without it. |  |
| `PKG004` | Warning | mimetype is not exactly an ASCII media type (stray whitespace or non-ASCII bytes). |  |
| `PKG005` | Warning | An optional package member is missing. |  |
| `PKG006` | Error | mimetype is not the first ZIP member. |  |
| `PKG007` | Error | mimetype is compressed. |  |
| `PKG008` | Error | A member the document needs is missing. |  |
| `PKG009` | Error | ZIP member names are duplicated. |  |
| `PKG010` | Error | A ZIP member name is absolute or escapes its directory. |  |
| `PKG011` | Warning | Declared signatures are unverified. |  |
| `PKG012` | Error | Manifest encryption prevents complete inspection. |  |
| `REF001` | Error | Reference destination is missing. |  |
| `REF002` | Error | Reference destination is ambiguous. |  |
| `REF003` | Error | Named range has inconsistent endpoints or identity. |  |
| `REF004` | Warning | Reference destination requires native scope review. |  |
| `REVISION001` | Error | Tracked-region identities are missing or contradictory. |  |
| `REVISION002` | Error | Tracked-region change-mark relationship is invalid. |  |
| `REVISION003` | Error | Change mark has no unique tracked-region declaration. |  |
| `REVISION004` | Warning | Tracked declaration has no established current-flow anchor. |  |
| `REVISION005` | Warning | Change anchor is inside an unestablished visibility context. |  |
| `REVISION006` | Warning | Tracked revision scope requires review. |  |
| `SCHEMA001` | Warning | A member does not validate against the ODF schema. |  |
| `SCHEMA002` | Info | No ODF schema is bundled for the declared version. |  |
| `SHEET001` | Error | Sheet has no name. | `sheet.name` |
| `SHEET002` | Warning | Sheet keeps its default name. | `sheet.name` |
| `SHEET003` | Warning | Empty sheet follows the last sheet with content. |  |
| `STYLE001` | Warning | Paragraph style scope or properties are unresolved. |  |
| `STYLE002` | Info | Empty paragraphs may be visual spacers. | `text.remove_spacers` |
| `STYLE003` | Error | Blinking text styling is declared. |  |
| `TABLE001` | Warning | Table intent or header relationships require native review. |  |
| `TABLE002` | Error | Table grid or header bands cannot be resolved safely. |  |
| `TABLE003` | Warning | Declared data table has no semantic headers. | `table.headers` |
| `TABLE004` | Warning | Data sheet marks no header rows. |  |
| `TABLE005` | Warning | Data sheet merges cells. |  |
| `XML001` | Error | A required XML member cannot be parsed. |  |

## Renamed in the next release

| Previous ID | Current IDs |
| --- | --- |
| `PKG000` | `PKG001` |
| `PKG001` | `PKG002`, `PKG003`, `PKG004` |
| `PKG002` | `PKG005` |
| `PKG003` | `PKG006` |
| `PKG004` | `PKG007` |
| `PKG005` | `PKG008` |
| `PKG006` | `PKG009` |
| `PKG007` | `PKG010` |
| `PKG008` | `PKG011` |
| `PKG009` | `PKG012` |
| `XML001` | `XML001` |
| `ODF001` | `ODF001` |
| `ODF002` | `ODF002` |
| `ODF003` | `ODF003`, `ODF004` |
| `ODF004` | `ODF005` |
| `ODF005` | `ODF006` |
| `ODF006` | `ODF007` |
| `ODF007` | `ODF008` |
| `ODF008` | `ODF009` |
| `ODF009` | `ODF010` |
| `ODF010` | `ODF011` |
| `ODF011` | `ODF012` |
| `SCHEMA001` | `SCHEMA001` |
| `SCHEMA002` | `SCHEMA002` |
| `NATIVE001` | `NATIVE001` |
| `NATIVE002` | `NATIVE002` |
| `META001` | `META001` |
| `META002` | `META002` |
| `META003` | `META003` |
| `META004` | `META004` |
| `HEADING001` | `HEADING001` |
| `HEADING002` | `HEADING002`, `HEADING003` |
| `HEADING003` | `HEADING004` |
| `HEADING004` | `HEADING005` |
| `NOTE001` | `NOTE001` |
| `REVISION002` | `REVISION001`, `REVISION002`, `REVISION003` |
| `REVISION003` | `REVISION004`, `REVISION005` |
| `HIDDEN002` | `ORDER001` |
| `ORDER001` | `ORDER002` |
| `REVISION001` | `REVISION006` |
| `HIDDEN001` | `ORDER003` |
| `STYLE001` | `STYLE001` |
| `GRAPHIC003` | `GRAPHIC001` |
| `TABLE001` | `TABLE001` |
| `TABLE002` | `TABLE002` |
| `TABLE003` | `TABLE003` |
| `LANG004` | `LANG001` |
| `LANG005` | `LANG002` |
| `REFERENCE001` | `REF001` |
| `REFERENCE002` | `REF002` |
| `REFERENCE003` | `REF003` |
| `REFERENCE004` | `REF004` |
| `NOTE002` | `NOTE002`, `NOTE003`, `NOTE004` |
| `LINK001` | `LINK001` |
| `LAYOUT001` | `STYLE002` |
| `STYLE002` | `STYLE003` |
| `SHEET001` | `SHEET001` |
| `SHEET002` | `SHEET002` |
| `TABLE004` | `TABLE004` |
| `TABLE005` | `TABLE005` |
| `LINK002` | `LINK002` |
| `SHEET007` | `SHEET003` |
| `PAGE001` | `PAGE001`, `PAGE002` |
| `PAGE002` | `PAGE003` |
| `GRAPHIC005` | `GRAPHIC002` |
| `PAGE003` | `PAGE004` |
| `PAGE004` | `PAGE005` |
| `LINK003` | `LINK003` |
| `MATH001` | `MATH001`, `MATH002` |
| `MATH002` | `MATH003` |
| `MATH003` | `MATH004` |
| `CHART001` | `CHART001`, `CHART002` |
| `CHART002` | `CHART003` |
| `CHART003` | `CHART004` |
| `CHART004` | `CHART005` |
| `CHART005` | `CHART006`, `CHART007` |
| `CHART006` | `CHART008`, `CHART009`, `CHART010`, `CHART011` |
| `IMAGE005` | `IMAGE001` |
| `IMAGE004` | `IMAGE002` |
| `IMAGE001` | `IMAGE003`, `IMAGE004` |
| `IMAGE003` | `IMAGE005` |
| `BASE001` | `DATABASE001`, `DATABASE002`, `DATABASE003` |
| `BASE002` | `DATABASE004` |
| `BASE003` | `DATABASE005`, `DATABASE006`, `DATABASE007` |
| `BASE004` | `DATABASE008`, `DATABASE009` |
| `BASE005` | `DATABASE010` |
| `BASE006` | `DATABASE011`, `DATABASE012` |
| `PDF000` | `PDF001` |
| `PDF001` | `PDF002` |
| `PDF002` | `PDF003` |
| `PDF003` | `PDF004` |
| `PDF004` | `PDF005` |
| `PDF005` | `PDF006` |
| `PDF006` | `PDF007` |
| `PDF007` | `PDF008` |
| `PDF008` | `PDF009` |
| `PDF009` | `PDF010` |
| `PDF010` | `PDF011` |
| `PDF011` | `PDF012` |
| `PDF012` | `PDF013` |
| `PDF013` | `PDF014` |
| `PDF014` | `PDF015` |
| `PDF015` | `PDF016` |
| `PDF016` | `PDF017` |
| `PDF017` | `PDF018` |
| `PDF018` | `PDF019` |
| `PDF019` | `PDF020` |
| `PDF020` | `PDF021` |
| `PDF021` | `PDF022` |
| `PDF022` | `PDF023` |
| `PDF023` | `PDF024` |
| `VERA001` | `PDFUA001` |
| `FID001` | `FIDELITY001` |
| `FID002` | `FIDELITY002` |
| `FID003` | `FIDELITY003` |
| `FID004` | `FIDELITY004` |
| `FID005` | `FIDELITY005` |
| `FID006` | `FIDELITY006` |
| `FID007` | `FIDELITY007` |
| `GRAPHIC001` | `GRAPHIC003` |
| `GRAPHIC002` | `GRAPHIC004` |
| `LIST001` | `LIST001`, `LIST002`, `LIST003`, `LIST004` |
| `LIST002` | `LIST005`, `LIST006` |
| `LIST003` | `LIST007`, `LIST008` |
| `LIST004` | `LIST009` |

## Reading findings

Errors fail checks; warnings fail strict gates. A registered rule can identify decision
kinds without guessing an answer. Read [plans](PLAN.md) and inspect the finding's actual
context before enabling a change. Source relationships, native output and PDF validation
remain separate; [accessibility boundaries](ACCESSIBILITY.md) explain measured limits.

`SCHEMA001` is a producer/differential-assurance warning, not a conformance certificate.
Text table classification uses declared data and actual grid/header relationships;
ambiguous cases require native editing. Spreadsheet data-sheet/default-name heuristics
remain scoped observations; they do not establish intended meaning. `VERA001` retains the
independent standard clause/test. The built-in PDF audit is a bounded smoke test.

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
split decoded names as path syntax. `N` is a one-based domain ordinal, not an XML child index. Use the printed target and
fingerprint; do not reconstruct it from decoded names or another reading context. `ref` is the
element's percent-encoded declared name (`table[name=Data]`, `frame[name=Logo]`) or, when it has none, its
index among tables or graphics (`table[2]`). `meta/title` and `meta/language` name the
missing or conflicting metadata field. `styles` covers style definitions wherever they are
stored, `package/mimetype` is the ZIP `mimetype` member, and `document` is a flat file or
a schema or parse defect in one. The text report prints `path` followed by the member in
parentheses, for example `manifest (META-INF/manifest.xml)`.
