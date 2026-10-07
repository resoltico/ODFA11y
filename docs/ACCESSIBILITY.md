# Accessibility scope and limits

ODFA11y works on an ODF Writer source and its PDF/UA-1 export. The source and the PDF
have separate structures, so both are inspected. A passing report means only that the
implemented checks found no errors; it is not an accessibility certificate.

## What each tool establishes

| Layer | Evidence provided | What still needs review |
| --- | --- | --- |
| ODT audit | Package/XML readability, version consistency, metadata, selected semantic properties; with `--schema`, validity against the bundled ODF schema. | Whether headings, table headers, links and descriptions convey the intended meaning. |
| ODT remediation | Explicit, typed changes with per-target outcomes; unchanged text; no new ODF schema violations. | Whether the choices were right, and the visual result. |
| LibreOffice export | A PDF produced with the requested PDF/UA and tagging options. | Whether this exporter and version produced correct accessible structure. |
| Built-in PDF audit | Metadata, tagging markers, structure roles, heading sequence, list/table shape, figure `/Alt`, link structure, extractable text. | Everything veraPDF and a person check; it is a smoke test, not PDF/UA validation. |
| veraPDF | Machine-verifiable PDF/UA-1 rules, each failure with its clause and test number. | Human checkpoints and the actual reading experience. |
| Fidelity comparison | Source and candidate renders agree on pages, text, links and rendered ink under the policy. | Whether an intended change looks right. |

The PDF audit resolves custom roles through `/RoleMap`, visits each structure object once
and parses strictly. It does not detect visible content missing from the structure tree;
that needs marked-content parsing and is veraPDF's job.

## ODF schema validation

The official OASIS ODF 1.3 and 1.4 Relax NG schemas ship unmodified with the package, with
their source URLs and SHA-256 digests recorded and verified by tests. `audit --schema`
validates every member against the schema for the declared version (versions without a
bundled schema are reported `ODF905`). Validation never touches the network.

LibreOffice output is not strictly schema-valid: even a plain document usually fails in
`styles.xml`. An absolute gate would therefore reject real inputs, so `ODF900` is a
warning and the gate that matters is *differential*: `remediate` compares violation
messages before and after and refuses a result with any violation the source did not have.
`document.odf_version` relabels the package; the result must still validate for the new
version. A relabelled or untouched document is "no new violations", never "ODF-conformant".

## Preservation boundaries

Remediation never invents alternative text, heading levels or table-header choices. It
does not split merged cells, repair heading hierarchies or remove manually typed
numbering. Table and link heuristics can produce false positives; review the finding in
context.

Only members an operation edits are re-serialized; every other member, and any foreign
markup, comments and processing instructions inside edited ones, is carried over. The text
guard compares the sequence of paragraph and heading strings after collapsing whitespace
and treating non-breaking spaces as spaces; graphic title and description are excluded. It
detects wording changes but is not a byte comparison, a rendering comparison or proof of
unchanged pagination: that is what [fidelity comparison](FIDELITY.md) adds.

## Threat model

Inputs are untrusted ZIP, XML and PDF files. ODT input is limited to 10,000 members and
256 MiB of declared uncompressed data, checked before loading; packages are never
extracted, so path traversal does not apply, and the writer refuses unsafe member names.
XML entity resolution and network access are disabled. LibreOffice and veraPDF are run
with argument lists (never a shell), a temporary profile and timeouts. Outputs are
published atomically, and a source is never overwritten.

These controls do not sandbox anything. Rendering for fidelity uses pdfium, native code
that parses PDFs, and veraPDF is a Java application; process untrusted documents in an
isolated environment with operating-system resource limits.

## Spacer removal

`remove_empty_spacers` is opt-in. It removes only empty body paragraphs without protected
graphic, bookmark, tab or break content, table/text-box/annotation/list ancestry, or page
or master-page style semantics. The text guard permits exactly the counted removals.
Removing spacers usually moves content, so the default fidelity gate flags it; review the
diff images and set `fidelity.pagination = "may-change"` when the movement is intended.

## Human acceptance

Before distribution, review:

- **Headings**: the actual hierarchy and navigation, not just the levels.
- **Alt text**: whether each description is meaningful in its context.
- **Reading order**, including footnotes, floating objects, tables and graphics.
- **Table headers**: whether they express the correct relationships.
- **Link purpose**: whether each link is understandable in context.
- **Colour**: whether colour carries information available nowhere else; contrast.
- **Layout**: typography, pagination and appearance, and behaviour with assistive technology.

A document can contain non-empty alternative text and tagged elements and still be
unusable. `REVIEW.md` in an [evidence bundle](EVIDENCE.md) carries this checklist.

## Standards and tool references

- [ODF 1.4 specification](https://docs.oasis-open.org/office/OpenDocument/v1.4/) and its [schemas](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/schemas/).
- [LibreOffice PDF/UA guidance](https://help.libreoffice.org/latest/en-US/text/shared/01/ref_pdf_export_universal_accessibility.html) and [PDF filter parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html).
- [veraPDF](https://docs.verapdf.org/): the PDF/UA validator.
- [pypdf](https://pypdf.readthedocs.io/en/stable/) and [pypdfium2](https://pypdfium2.readthedocs.io/): PDF parsing and rendering.
