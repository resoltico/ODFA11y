# Accessibility scope and limits

ODFA11y targets an ODF 1.4 Writer source and a PDF/UA-1 export. The source and PDF
have separate structures, so both need inspection. A report passing means only
that its implemented error checks found no errors; it is not an accessibility
certificate.

## What the tools establish

| Layer | Evidence provided | What still needs review |
| --- | --- | --- |
| ODT audit | Package/XML readability, version declarations, metadata and selected semantic properties. Optional Relax NG validation checks supplied schemas. | Whether headings, table headers, links and descriptions convey the intended meaning. |
| ODT remediation | Explicit metadata, hyperlink, graphic-description, header-row and spacing changes, with a normalized text guard. | Correct choices, typography, page breaks and visual appearance after editing. |
| LibreOffice export | A PDF produced using the requested PDF/UA and tagging filter options. | Whether this exporter/version produced correct accessible structure. |
| pypdf diagnostics | Parsed PDF metadata, tagging markers, reachable structure roles, Figure `/Alt`, link counts and extractable text. | Complete PDF/UA requirements, reading order and semantic quality. |
| veraPDF | Machine-verifiable results for the requested PDF/UA-1 profile. | Human checkpoints and the user's actual reading experience. |

The PDF inspector resolves custom roles through `/RoleMap`, including custom
roles that resolve to Figure or numbered headings. Cyclic or unmapped role chains
produce findings; repeated structure-tree objects are visited once. Link counts
and extractable-text counts are observations, not guarantees of usable navigation
or correct reading order. PDF parsing uses pypdf's strict mode.

## Preservation boundaries

Remediation never invents alternative text, heading levels or table-header choices.
It does not automatically split merged cells, repair heading hierarchies or remove
manually typed numbering. Table and link heuristics can produce false positives;
review the finding in its document context.

The text guard compares the sequence of paragraph/heading strings after collapsing
whitespace and treating nonbreaking spaces as ordinary spaces. Graphic title and
description metadata are excluded. This detects many wording changes but is not
a byte-for-byte comparison, a rendering comparison or proof of unchanged
pagination. Changing spacing, headers or hyperlinks can affect layout.

ODT input is limited to 10,000 ZIP members and 256 MiB of declared uncompressed
member data, checked before loading member contents. Larger documents are rejected;
these bounds do not replace process isolation and resource limits for hostile inputs.
Ambiguous duplicate ZIP names cannot be rewritten.

The ODT writer validates the rewritten ZIP, places `mimetype` first and stores it
uncompressed before replacing the destination. It preserves member metadata and
compression where possible, not byte identity. Using the same source and
destination path can replace the original; use separate paths for review.

Version remediation changes declarations. It is not a complete conversion of all
ODF constructs. Schemas are external and validation is opt-in; declaring `1.4`
does not establish ODF 1.4 conformance.

## Spacer removal

`--remove-empty-spacers` is opt-in. It removes only empty body paragraphs without
protected graphic/bookmark/tab/break content, table/text-box/annotation/list ancestry,
or page/master-page style semantics. The wording guard permits exactly the counted
empty-block removals while preserving all other normalized blocks and their order.
Review pagination and layout after enabling it; keep it disabled when their role
has not been established.

## Human acceptance

Before distribution, review:

- The actual heading hierarchy and navigation.
- Reading order, including footnotes, tables and graphics.
- Whether table headers express the correct relationships.
- Alternative-text meaning and link purpose in context.
- Contrast, colour-only meaning, typography and pagination.
- Text selection and the document's behavior with assistive technology.

A document can contain nonempty alternative text and tagged elements yet remain
unusable. Treat automated reports as evidence for specific checks, with human
review completing the acceptance process.

## Standards and tool references

- [ODF 1.4 specification](https://docs.oasis-open.org/office/OpenDocument/v1.4/): source package and XML format.
- [LibreOffice PDF/UA guidance](https://help.libreoffice.org/latest/en-US/text/shared/01/ref_pdf_export_universal_accessibility.html): source-document/export expectations.
- [LibreOffice PDF filter parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html): requested export options.
- [pypdf documentation](https://pypdf.readthedocs.io/en/stable/): PDF parsing, text and metadata APIs.
- [veraPDF validation](https://docs.verapdf.org/validation/): standards validation and its scope.

LibreOffice and validator behavior can change with their versions. Retain tool
versions with production evidence when reproducibility matters. Python dependency
locking does not freeze external applications or operating-system images.
