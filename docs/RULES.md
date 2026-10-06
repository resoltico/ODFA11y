# Rule reference

Reports use stable rule IDs, severity, a message and optional location/details.
`fixable` is a hint about mechanical support, not a repair promise or an instruction
to bypass review. Use [the workflow](WORKFLOW.md) to interpret reports and exit
statuses; implementation is authoritative if a reference and code disagree.

## Package and XML

These findings are errors.

| ID | Finding |
| --- | --- |
| `PKG000` | Source is not a readable ODT/ZIP package. |
| `PKG001` | Required `mimetype` member is missing. |
| `PKG002` | MIME type is not `application/vnd.oasis.opendocument.text`. |
| `PKG003` | `mimetype` is not the first ZIP member. |
| `PKG004` | `mimetype` is compressed. |
| `PKG005` | A required XML member is missing. |
| `PKG006` | ZIP member names are duplicated. |
| `XML001` | A required XML member, or settings XML when present, cannot be parsed. |

Rewriting valid loaded packages restores the mimetype ordering/compression
invariant. Missing members, malformed XML and duplicate entries require diagnosis;
there is no general package reconstruction command. Duplicate members are reported
but rejected on rewrite; oversize or corrupt packages produce `PKG000`.

## ODF declarations and metadata

| ID | Severity | Finding |
| --- | --- | --- |
| `ODF001` | Error | Core XML or manifest declaration differs from the target ODF version. |
| `ODF002` | Error | Manifest root file-entry `/` is missing. |
| `ODF003` | Error | Manifest root file-entry version differs from the target. |
| `ODF004` | Error | Manifest root media type is not the ODT media type. |
| `ODF900` | Error | Supplied main schema is missing, cannot load, or rejects an XML member. |
| `ODF901` | Error | Supplied manifest schema is missing, cannot load, or rejects the manifest. |
| `META001` | Error | Nonempty title metadata is missing. |
| `META002` | Error | Language is absent from both metadata and the default paragraph style. |
| `META003` | Warning | Metadata and default paragraph-style languages disagree. |

Remediation can update declarations and explicitly supplied metadata. It does not
create a missing manifest root entry or perform a complete ODF-version conversion.

## Semantics and layout

| ID | Severity | Finding |
| --- | --- | --- |
| `SEM001` | Error | Heading outline level is absent, nonnumeric or below one. |
| `SEM002` | Error | First heading starts deeper than level one, or a later level skips hierarchy. |
| `SEM003` | Warning | Heading text heuristically resembles manually typed numbering. |
| `SEM004` | Info | No structural headings were found. |
| `SEM005` | Warning | Footnotes/endnotes need reading-order and export review. |
| `IMG001` | Error | Graphic frame has neither a nonempty accessible title nor description. |
| `TBL001` | Error | Table has merged/spanned/covered-cell structures requiring review. |
| `TBL002` | Warning | Table appears data-like but has no direct semantic header rows. |
| `LNK001` | Warning | Visible URL/email text appears outside hyperlink representation. |
| `LAY001` | Info | Empty paragraphs outside cells, text boxes and annotations may be spacers. |
| `STYLE001` | Error | Blinking text styling is declared. |

Heading-numbering, table and link findings use heuristics; inspect the source in
context. Graphics need supplied descriptions. Header wrapping requires a named
table and explicit row count. `LAY001` is observational: [spacer removal](ACCESSIBILITY.md#spacer-removal)
is explicit and preserves protected structures.

## PDF and veraPDF

| ID | Severity | Finding |
| --- | --- | --- |
| `PDF000` | Error | PDF cannot be opened or strictly inspected. |
| `PDF001` | Error | Nonempty document title is missing. |
| `PDF002` | Error | Catalog language is missing or empty. |
| `PDF003` | Error | `/MarkInfo /Marked true` is absent. |
| `PDF004` | Error | Structure-root dictionary is absent or empty. |
| `PDF005` | Warning | `/DisplayDocTitle true` viewer preference is absent. |
| `PDF006` | Error | XMP does not declare PDF/UA part 1. |
| `PDF007` | Error | A reachable Figure role has no nonempty `/Alt`, including mapped custom roles. |
| `PDF008` | Info | No numbered heading structure roles were detected. |
| `PDF009` | Error | PDF has no pages. |
| `PDF010` | Error | Pages have no extractable text. |
| `PDF011` | Error | A custom structure role does not resolve to a standard role. |
| `VERA000` | Warning | Requested veraPDF executable is unavailable. |
| `VERA001` | Error | veraPDF reports PDF/UA-1 machine non-conformance. |

PDF inspection records link counts without requiring that every document contain
links. A clean report is not complete PDF/UA validation. veraPDF process/XML errors
can be execution failures instead of `VERA001`; check stderr and the exit status.
