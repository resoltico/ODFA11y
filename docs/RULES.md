# Rule reference

Every finding comes from one registered rule (the identifier prefix names its owner: `PKG`, `XML`, `ODF` and `META` belong to the ODF core, `TXT` to the text family, `PDF`, `VERA` and `FID` to the output checks) with a stable ID, a severity, a category and,
where a configuration can address it, a **remedy**: the configuration key that holds the
decision. Severity decides exit statuses (see [the workflow](WORKFLOW.md#exit-statuses));
the code registry in [rules.py](../src/odfa11y/report/rules.py) is authoritative and a test
checks that this document lists exactly its rules and severities.

## Package and XML

These apply to every ODF document, whatever its family.

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `PKG000` | Error | Source is not a readable ODF package or flat XML document. |  |
| `PKG001` | Warning | The document does not declare its media type. |  |
| `PKG002` | Warning | An optional package member is missing. |  |
| `PKG003` | Error | mimetype is not the first ZIP member. |  |
| `PKG004` | Error | mimetype is compressed. |  |
| `PKG005` | Error | A member the document needs is missing. |  |
| `PKG006` | Error | ZIP member names are duplicated. |  |
| `PKG007` | Error | A ZIP member name is absolute or escapes its directory. |  |
| `XML001` | Error | A required XML member cannot be parsed. |  |

## ODF declarations, kind, schema and metadata

Also common to every family. `ODF009` says that a document's family has no semantic audit yet: the common checks ran and nothing is implied about the rest.

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `ODF001` | Error | Package members declare different ODF versions. | `document.odf_version` |
| `ODF002` | Error | Manifest root file-entry '/' is missing. |  |
| `ODF003` | Error | Manifest root file-entry version differs from the document version. | `document.odf_version` |
| `ODF004` | Error | Manifest root media type differs from the document's. |  |
| `ODF005` | Error | The media type is not an OpenDocument document type. |  |
| `ODF006` | Error | The document body does not match its media type. |  |
| `ODF007` | Warning | The file extension does not match the media type. |  |
| `ODF008` | Warning | The document kind is deprecated or legacy. |  |
| `ODF009` | Info | No semantic audit exists for this document family. |  |
| `ODF010` | Error | A flat XML document's root is not office:document. |  |
| `ODF011` | Error | A package's content root is not office:document-content. |  |
| `ODF900` | Warning | A member does not validate against the ODF schema. |  |
| `ODF905` | Info | No ODF schema is bundled for the declared version. |  |
| `META001` | Error | Document title metadata is missing. | `document.title` |
| `META002` | Error | Document language is not declared. | `document.language` |
| `META003` | Warning | Metadata and default style languages disagree. | `document.language` |

## Text documents

Owned by the text family (`TXT`). A document of another family never produces them. Remedies are keys of the `[text]` configuration table.

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `TXT001` | Error | Heading has no valid outline level. |  |
| `TXT002` | Error | Heading hierarchy starts too deep or skips a level. |  |
| `TXT003` | Warning | Heading text resembles manually typed numbering. |  |
| `TXT004` | Info | No structural headings were found. |  |
| `TXT005` | Warning | Footnotes or endnotes need reading-order review. |  |
| `TXT010` | Error | Graphic has neither accessible title nor description. | `text.alt_text` |
| `TXT020` | Error | Table has merged or split cells. |  |
| `TXT021` | Warning | Data-like table has no header rows. | `text.table_headers` |
| `TXT030` | Warning | Visible URL or email address is not a hyperlink. | `text.remediation.linkify_plain_addresses` |
| `TXT040` | Info | Empty paragraphs may be visual spacers. | `text.remediation.remove_empty_spacers` |
| `TXT050` | Error | Blinking text styling is declared. |  |

## PDF inspection and veraPDF

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
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
| `PDF010` | Error | No extractable text was found. |  |
| `PDF011` | Error | A custom structure role does not resolve to a standard role. |  |
| `PDF012` | Error | Heading structure starts too deep or skips a level. |  |
| `PDF013` | Error | List structure is malformed. |  |
| `PDF014` | Error | Table structure is malformed. |  |
| `PDF015` | Warning | Table has no header cells. |  |
| `PDF016` | Warning | A link annotation is not represented by a Link element. |  |
| `PDF017` | Warning | A Link structure element refers to no link annotation. |  |
| `PDF018` | Error | A link annotation is referenced from another page. |  |
| `PDF019` | Error | A link has no alternate description. |  |
| `VERA000` | Warning | The requested veraPDF validator is unavailable. |  |
| `VERA001` | Error | veraPDF reports a failed PDF/UA-1 rule. |  |

## Fidelity comparison

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `FID001` | Error | Page count differs. |  |
| `FID002` | Error | Page dimensions differ. |  |
| `FID003` | Error | Document text differs. |  |
| `FID004` | Error | A source link is missing or changed. |  |
| `FID005` | Error | Rendered page differs beyond the tolerance. |  |
| `FID006` | Info | Links were added. |  |
| `FID007` | Error | A page is too large to render for comparison. |  |

## Reading findings

`ODF900` is a warning because pristine LibreOffice output often fails the strict ODF
schema (for example in `styles.xml`); the schema matters most as a *regression* gate,
which `remediate` enforces: it refuses any result with a violation the source did not
already have. The `TXT` link, table, numbering and spacer findings use heuristics; inspect the
source in context. Graphics need supplied descriptions, and header rows need a named
table with an explicit row count. `TXT040` is observational: [spacer
removal](ACCESSIBILITY.md#spacer-removal) is explicit and preserves protected structures.
`VERA001` appears once per failed veraPDF rule and keeps the standard's clause and test
number in its details. `PDF` findings are a fast smoke test, not PDF/UA validation.

## Locations

A finding's `location` is logical, so the same document audits to the same locations as a
package (`.odt`) and as flat XML (`.fodt`). It has a `path` and an optional `member`, the
stored package member, which is set only where that physical detail helps (package-level
defects such as `ODF004` or `PKG004`). A finding with no location applies to the whole
file; an audit reports no location at all for a source it cannot open.

```text
path     = part [ "/" segment ]
part     = "content" | "styles" | "meta" | "manifest" | "package" | "document"
segment  = "heading[" N "]" | "paragraph[" N "]" | "table[" ref "]" | "frame[" ref "]"
         | "title" | "language" | "mimetype"
ref      = name | "#" N
```

`N` counts from 1 in document order, separately for each kind: `heading[2]` is the second
`text:h`, `paragraph[3]` the third `text:p` (headings are not paragraphs here). `ref` is the
element's declared name (`table[Data]`, `frame[Logo]`) or, when it has none, `#` and its
index among tables or graphics (`table[#2]`). `meta/title` and `meta/language` name the
missing or conflicting metadata field. `styles` covers style definitions wherever they are
stored, `package/mimetype` is the ZIP `mimetype` member, and `document` is a flat file or
a schema or parse defect in one. The text report prints `path` followed by the member in
parentheses, for example `manifest (META-INF/manifest.xml)`.
