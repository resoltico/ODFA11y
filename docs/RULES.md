# Rule reference

Every finding comes from one registered rule with a stable ID, a severity, a category and,
where a configuration can address it, a **remedy**: the configuration key that holds the
decision. Severity decides exit statuses (see [the workflow](WORKFLOW.md#exit-statuses));
the code registry in [rules.py](../src/odfa11y/report/rules.py) is authoritative and a test
checks that this document lists exactly its rules and severities.

## Package and XML

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `PKG000` | Error | The source cannot be read as an ODT package (corrupt, oversized or not a ZIP). |  |
| `PKG001` | Error | Required mimetype member is missing. |  |
| `PKG002` | Error | MIME type is not application/vnd.oasis.opendocument.text. |  |
| `PKG003` | Error | mimetype is not the first ZIP member. |  |
| `PKG004` | Error | mimetype is compressed. |  |
| `PKG005` | Error | A required XML member is missing. |  |
| `PKG006` | Error | ZIP member names are duplicated. |  |
| `PKG007` | Error | Names such as `/etc/x` or `../x` are unsafe if the package is ever extracted; the writer refuses them. |  |
| `XML001` | Error | A required XML member cannot be parsed. |  |

## ODF declarations, schema and metadata

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `ODF001` | Error | Package members declare different ODF versions. | `document.odf_version` |
| `ODF002` | Error | Manifest root file-entry '/' is missing. |  |
| `ODF003` | Error | Manifest root file-entry version differs from the document version. | `document.odf_version` |
| `ODF004` | Error | Manifest root media type is not the ODT media type. |  |
| `ODF900` | Warning | A member does not validate against the ODF schema. |  |
| `ODF905` | Info | No ODF schema is bundled for the declared version. |  |
| `META001` | Error | Document title metadata is missing. | `document.title` |
| `META002` | Error | Document language is not declared. | `document.language` |
| `META003` | Warning | Metadata and default paragraph-style languages disagree. | `document.language` |

## Semantics, links and layout

| ID | Severity | Finding | Remedy |
| --- | --- | --- | --- |
| `SEM001` | Error | Heading has no valid outline level. |  |
| `SEM002` | Error | Heading hierarchy starts too deep or skips a level. |  |
| `SEM003` | Warning | Heading text resembles manually typed numbering. |  |
| `SEM004` | Info | No structural headings were found. |  |
| `SEM005` | Warning | Footnotes or endnotes need reading-order review. |  |
| `IMG001` | Error | Graphic has neither accessible title nor description. | `alt_text` |
| `TBL001` | Error | Table has merged or split cells. |  |
| `TBL002` | Warning | Data-like table has no header rows. | `table_headers` |
| `LNK001` | Warning | Visible URL or email address is not a hyperlink. | `remediation.linkify_plain_addresses` |
| `LAY001` | Info | Empty paragraphs may be visual spacers. | `remediation.remove_empty_spacers` |
| `STYLE001` | Error | Blinking text styling is declared. |  |

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
| `PDF016` | Warning | Link annotations have no Link structure elements. |  |
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
already have. The `LNK`, `TBL`, `SEM003` and `LAY` findings use heuristics; inspect the
source in context. Graphics need supplied descriptions, and header rows need a named
table with an explicit row count. `LAY001` is observational: [spacer
removal](ACCESSIBILITY.md#spacer-removal) is explicit and preserves protected structures.
`VERA001` appears once per failed veraPDF rule and keeps the standard's clause and test
number in its details. `PDF` findings are a fast smoke test, not PDF/UA validation.
