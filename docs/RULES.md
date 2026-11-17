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
| `FIDELITY008` | Error | A URI destination cannot be established. |  |
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
| `NATIVE002` | Warning | Private export cannot preserve filename/path fields. |  |
| `NATIVE003` | Warning | Relative hyperlink destinations are unestablished for private export. |  |
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
| `PDF013` | Error | The first numbered PDF heading starts below level one. |  |
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
| `PDF025` | Error | Numbered PDF heading hierarchy skips a level. |  |
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

## Reading findings

Errors fail checks; warnings fail strict gates. A registered rule can identify decision
kinds without guessing an answer. Read [plans](PLAN.md) and inspect the finding's actual
context before enabling a change. Source relationships, native output and PDF validation
remain separate; [accessibility boundaries](ACCESSIBILITY.md) explain measured limits.

`SCHEMA001` is a producer/differential-assurance warning, not a conformance certificate.
Text table classification uses declared data and actual grid/header relationships;
ambiguous cases require native editing. Spreadsheet data-sheet/default-name heuristics
remain scoped observations; they do not establish intended meaning. `PDFUA001` retains the
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
