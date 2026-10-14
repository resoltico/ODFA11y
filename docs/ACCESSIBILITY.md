# Accessibility scope and limits

ODFA11y works on an OpenDocument source and its PDF/UA-1 export. The source and the PDF
have separate structures, so both are inspected. A passing report means only that the
implemented checks found no errors; it is not an accessibility certificate.

## What each tool establishes

| Layer | Evidence provided | What still needs review |
| --- | --- | --- |
| ODF audit | Package/XML readability, document kind, version consistency, metadata; selected semantic properties for all eight families; with `--schema`, validity against the bundled ODF schema. | Whether headings, table headers, sheet names, links and descriptions convey the intended meaning. |
| ODF remediation | Explicit, typed changes with per-target outcomes; unchanged content; no new ODF schema violations. | Whether the choices were right, and the visual result. |
| LibreOffice export | A PDF produced with the requested PDF/UA and tagging options. | Whether this exporter and version produced correct accessible structure. |
| Built-in PDF audit | Metadata, tagging markers, structure roles, heading sequence, list/table shape, figure `/Alt`, that every link annotation has a Link element referring to it on its page and a description (`/Contents` or the element's `/Alt`), that marked content on each page and the structure tree's references to it correspond and that no text is shown outside tagged content and artifacts, extractable text or described inspected graphical content. | Everything veraPDF and a person check; it is a smoke test, not PDF/UA validation. |
| veraPDF | Machine-verifiable PDF/UA-1 rules, each failure with its clause and test number. | Human checkpoints and the actual reading experience. |
| Fidelity comparison | Source and candidate renders agree on pages, text, links and rendered ink under the policy. | Whether an intended change looks right. |

The PDF audit resolves custom roles through `/RoleMap`, visits each structure object once
and parses strictly. Links are checked by correspondence, not by count: each annotation must
be referenced by a Link element's `/OBJR` on the annotation's page. Content is reconciled
the same way: each page's content stream is scanned for marked-content sequences, and the
audit reports MCIDs that no structure element refers to (`PDF020`), references to MCIDs the
page lacks (`PDF021`), MCIDs referred to more than once (`PDF022`) and text shown outside
tagged content and `/Artifact` (`PDF023`). Invoked Form XObjects are scanned in their resource scopes, including nested and reused
Forms. Page and Form MCIDs have distinct identities; `/Stm` references are reconciled against
invoked streams. Leaf references count per incoming ownership edge while structure elements
expand once and active-path array cycle protection bounds shared-container traversal. Whether tagged
content is in a sensible reading order, or is correctly an artifact, stays with veraPDF and
a person.

Marked-content scanning skips raw inline images using their sample dimensions. Filtered
inline images or unsupported inline color spaces produce `PDF000` rather than guessing
where binary samples end. Whole-object Form ownership (`/StructParent`, rather than MCID sequences) is not reconciled
and produces explicit incomplete inspection. Cyclic Forms, excessive depth/invocations and unsupported parser
recursion produce explicit failed inspection. Unsupported stream decoding and malformed
decoder-parameter type errors are normalized at the shared stream boundary; they produce
`PDF000` in audit and controlled execution failure in comparison. The 64 MiB budget counts unique decoded page,
invoked Form, XMP, text CMap/encoding and applicable embedded Type1 font bytes. A separate 64 MiB content-work bound charges
repeated page/Form invocations; at most 10,000 streams per content array, 5,000 Form
invocations per document and 50 nested Forms are inspected. Audit and fidelity enforce this
preflight for tagged and untagged PDFs. pypdf's scoped decoder controls limit supported
filter outputs before decoding; final-byte accounting also rejects over-limit cached or
other decoded data. These controls do not bound total peak memory or rendering allocations.
The inspector establishes content correspondence and actual nonartifact graphic operations,
not pixel visibility, reading order or PDF/UA conformance.


## Link descriptions

LibreOffice **26.8 or newer** is required. Older installations and versions that cannot
be identified are rejected before conversion. Source link purpose comes from visible
labels, graphic alternatives and native `office:title`; `office:name` is a target name
and alone does not establish source purpose. Explicit link-description decisions set
`office:title`, preserve existing Names and never invent link purpose.

`odfa11y doctor` exports a synthetic link with `office:title` and checks whether its PDF/UA-1
description survives. Text pipeline exports run this self-test once and record
`pdfua_link_descriptions: supported | unsupported` under `toolchain.LibreOffice` in
`run.json`. Probe files are excluded. Execution failures fail the export stage.

The controlled LibreOffice 26.8.1.1 experiment exported both a supplied `office:title` and
an independent missing-title control without the PDF link alternative. Both retained
`PDF019` and failed veraPDF validation. The source decision remains valid; the actual PDF
failure remains an error. Existing meaningful Names can affect Writer's PDF export, as
shown by the [unnamed-link reproduction](../tests/reproductions/unnamed-link.odt) and its
named control, but changing Names can affect references and is outside automatic remediation.
[Bug 161583](https://bugs.documentfoundation.org/show_bug.cgi?id=161583#c17) records that
exporter limitation. A capability verdict measures the native title field, not every
possible authored link or a waiver of document-level PDF checks.

## Graphic roles

Effective decorative roles are resolved from ODF defaults, common and automatic styles,
legal parent inheritance and ordered class overlays. Broken, ambiguous or unsupported
contexts produce `GRAPHIC001` and role edits refuse. An explicit role is stored using
ODF 1.4 `draw:decorative` on `style:graphic-properties`; no extension namespace or silent
upgrade is used. Each changed target receives an isolated, proven style derivation.
Decorative declarations remove only the missing-alternative requirement. They do not
hide external resources, missing or malformed payloads, scripts, interactivity or page
navigation completeness. Existing group declarations require review and do not suppress
child findings. Preserved authored alternatives on a decorative object produce `GRAPHIC002`.
A standalone all-decorative image does not establish meaningful PDF content.

The controlled LibreOffice 26.8.1.1 mixed-image experiment retained meaningful text, the
described image and decoded pixels. With explicitly established visual styles, raster,
text and link fidelity passed. The native standard decorative property still exported as
an undescribed Figure: `PDF007` and veraPDF failures remained. The missing-role control
independently failed. Source role correctness therefore does not establish strict PDF/UA
success on that runtime. The production checks retain those failures; successful native
export of standard decorative roles remains an unresolved exporter condition.

## Document families

Every ODF kind is recognised from its declared media type, as a package or as flat XML,
and gets the common checks. Semantic audit and explicit remediation exist for all eight families. Text, spreadsheet,
presentation and drawing have native PDF filters. Formula has native MathML semantics,
but its current PDF export lacks required tagging and fails assurance. Chart, Image and
Base support source inspection/remediation only: required production PDF stages fail.
Base never opens connections, executes SQL or runs macros. Source correctness does not
certify embedded opaque documents or database storage. See [configuration](CONFIGURATION.md).

### Spreadsheets

The `SHEET` rules check what can be read from the source: sheet names (empty or default),
header rows and merged cells on sheets that look like tables of data, pictures and charts
without a title or description, link text that is a raw address, empty sheets after the last
one with content, and hidden sheets, rows and columns. They do not judge whether a sheet
name, a header label or a description is good, do not inspect formulas, charts' data or
conditional formatting, and do not look at drawn shapes. Two operations exist: renaming
sheets (refused for any sheet that is referred to by name, see
[Configuration](CONFIGURATION.md#renaming-sheets)) and describing frames. Merged cells,
header rows, link text and hidden content are reported but not changed.

### Spreadsheet PDF exports

Spreadsheets use LibreOffice's `calc_pdf_Export` filter and the same PDF audit, veraPDF
and fidelity gates as text documents. Checks describe the actual exporter output; source
header rows or alt text alone do not establish PDF/UA conformance.

With LibreOffice 26.8.0.3 and the pinned veraPDF 1.30.3, the tested table export has tagged cells but
no `TH` cells (`PDF015`), and veraPDF reports inconsistent table-column counts (7.2-43).
The `production` profile rejects the table-header warning before reaching veraPDF.
Integration tests require that failure and reject unrelated validator failures.

Fidelity comparisons check pages, text, links and ink. Calc's default header prints the
sheet name, so a rename changes rendered text (`FID003`). Change or remove the header in
Calc first, or use `remediate` and review the printed result. No warning or error is
whitelisted. An earlier failed gate leaves downstream stages `skipped`; a green integration
test can prove correct rejection of an invalid export.

## ODF schema validation

The official OASIS ODF 1.3 and 1.4 Relax NG schemas ship unmodified with the package, with
their source URLs and SHA-256 digests recorded and verified by tests. `audit --schema`
validates every member against the schema for the declared version (versions without a
bundled schema are reported `ODF905`). Validation never touches the network.

LibreOffice output is not strictly schema-valid: even a plain document usually fails in
`styles.xml`. An absolute gate would therefore reject real inputs, so `ODF900` is a
warning and the gate that matters is *differential*: `remediate` compares violations
before and after and refuses a result with any violation the source did not have. A
violation is identified by its message and a fingerprint of the failing element (its tag,
attributes, parent and neighbouring tags), not by a position, so fixing one violation
cannot hide an equal one introduced elsewhere, while edits elsewhere do not make an old
violation look new. libxml2 reports only the first error of a failing content model, so a
second error inside an element that already failed is outside what this gate can see;
violations it cannot locate are compared by count and reported as unlocated. Formula
documents validate native expressions against the bundled normative W3C MathML 3 grammar.
`document.odf_version` relabels the package; the result must still validate for the new
version. A relabelled or untouched document is "no new violations", never "ODF-conformant".

## Preservation boundaries

Remediation never invents alternative text, heading levels or table-header choices. It
does not split merged cells, repair heading hierarchies or remove manually typed
numbering. Table and link heuristics can produce false positives; review the finding in
context.

Only members an operation edits are re-serialized; every other member, and any foreign
markup, comments and processing instructions inside edited ones, is protected. Text editing
checks ordered normalized words (ODF spaces, tabs and line breaks retain word boundaries),
logical table grids and operation-specific protected XML facts. Existing destinations,
anchors, fields, geometry, payload references, excluded history/annotation/note content and
unrelated styles cannot disappear because visible words happen to match. Only the requested
metadata, proven style derivation, exact permitted address wrappers, reviewed heading/header
changes and counted inert-spacer removal normalize for the applicable operation.

Other families protect their meaning-specific XML facts: spreadsheet values/formulas/grids,
page shapes and navigation, MathML expressions, chart data and database bindings/settings.
Opaque payloads remain protected separately. These guards are not byte or rendering
comparisons; [fidelity comparison](FIDELITY.md) checks the publication's appearance.

Declared signatures (`PKG008`) remain unverified: no signature structure/reference,
cryptographic or trust validation is performed. Every guarded remediation, including dry
runs and empty/no-op plans, refuses signed packages. Original native export remains subject
to its ordinary guard and makes no signature claim; neither exported PDF nor evidence is
signed by a source signature. Manifest encryption (`PKG009`) blocks complete inspection,
template planning, remediation and guarded native export before ciphertext is parsed as
body XML. Duplicate names (`PKG006`) and unsafe archive paths (`PKG007`) also prevent
a complete inspection view and refuse guarded planning, remediation and native work before
manifest or body selection. Malformed manifests remain malformed, never assumed
unsigned/unencrypted.

Tracked declarations/markers permit only title/description metadata edits. Language,
version and other operations refuse before the first edit. The main outline and spacing/
spacer edits exclude notes, text boxes, annotation/history and hidden/conditional branches.
Graphic/link/table decisions and address linkification include current note bodies and
text boxes, with context-qualified locations, but exclude annotation/history/conditional
branches. `TXT060`/`TXT061` keep scope uncertainty visible for human review.

## Threat model

Inputs are untrusted ZIP, XML and PDF files. Package input is limited to 10,000 members and
256 MiB of declared uncompressed data, and a flat XML file to 256 MiB, checked before
loading; packages are never extracted, so path traversal does not apply, and the writer
refuses unsafe member names. PDF input is limited to 256 MiB, 5,000 pages and 500,000
structure elements. The XML parser disables entity resolution and network access. This does not deny network
access to LibreOffice, veraPDF, pdfium or other native importers. LibreOffice and
veraPDF are run with argument lists (never a shell), a temporary profile and timeouts, their
output is captured only up to a size limit, and a timed-out run has its whole process tree
killed (on Windows through `taskkill`). Outputs are published atomically, a source is never
overwritten, and evidence diagnostics redact local directories and are not read through links outside it
(see [Evidence](EVIDENCE.md)).

These controls do not sandbox anything and set no CPU or memory limit (a limit that
LibreOffice or a Java runtime tolerates is not portable). Rendering for fidelity uses
pdfium, native code that parses PDFs, and veraPDF is a Java application; process untrusted
documents in an isolated environment with operating-system resource limits.

## Spacer removal

`remove_empty_spacers` is opt-in. It removes only empty body paragraphs without protected
graphic, bookmark, tab or break content, table/text-box/annotation/list ancestry, or page
or master-page style semantics. XML identities, RDF metadata, conditional/class style references
and unrecognized paragraph or inline attributes also prevent removal. The text guard permits
exactly the counted removals of established inert paragraphs.
Removing spacers usually moves content, so the default fidelity gate flags it; review the
diff images and set `fidelity.pagination = "may-change"` when the movement is intended.

## Human acceptance

Before distribution, review:

- **Headings**: the actual hierarchy and navigation, not just the levels.
- **Alt text**: whether each description is meaningful in its context.
- **Reading order**, including footnotes, floating objects, tables and graphics; for a
  spreadsheet, the order of sheets, rows and columns.
- **Table headers**: whether they express the correct relationships; for a spreadsheet,
  whether the first row and column labels describe the data on every sheet.
- **Sheet names and hidden content** (spreadsheets): whether each name says what the sheet
  holds, and whether hidden sheets, rows and columns hold nothing a reader needs.
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

## Native document context and declared dependencies

The declaration preflight admits inline data and correctly addressed package targets without
an unestablished XML rendering base; admission does not prove decoding or native loading. Declaration
recognition includes unused fill/bullet images, chart symbols, SVG definitions and non-XLink
form image data. Files and embedded subdocument directories have distinct addressing rules;
presence does not establish payload decodability. Known external/unresolved/wrong-shape or
unestablished dynamic references are reported by `ODF012` and refused before guarded export;
ordinary navigational links are not automatic-fetch dependencies. Filename/path fields are
reported by `ODF013` and refused in captured pipeline export. Direct export of the original
can preserve original logical identity; `inspect` preserves authored fields and references.
See [Evidence](EVIDENCE.md#no-local-paths) for the authoritative policy boundary, capture
file-identity checks, stable ancestor-namespace prerequisite, comparison identity and portability.
The low-level `export_pdfua()` API is the raw application boundary; callers must apply their
own resource policy and native isolation. Core `export_document`, `compare_documents`
and pipeline stages own the shared guard; the CLI calls those guarded operations.

The controlled macOS LibreOffice 26.8.0.3 experiment retained intended 4x4 RGB embedded images
in flat and native-package positives. Its local/loopback external references did not retain
those images, and no request was observed; equal missing assets were not retention controls.
A separate healthy loopback responder proved observation was functional. These observations
are configuration-specific; an older 25.2 report of a fetch is supplementary unsupported-runtime
evidence. Run `uv run --no-sync python -m tools.probe_native_resources OUTPUT` in the supported
native environment to retain actual PDFs, decoded-pixel hashes, options and tool identities.
Linux/Windows observations require their own execution before cross-platform resource claims.
Neither the `production` assurance profile nor this URI preflight is an offline/confidential
sandbox. Native tools must run under caller-controlled isolation for untrusted inputs.

Native execution uses a finite positive per-invocation timeout. Core and CLI work options,
`audit_document` and `check_pdfua` default to 120 seconds and apply the selected value to
both LibreOffice export/capability probes and veraPDF validation. Direct `validate_pdfua`
retains its 180-second default. CLI `--timeout` accepts whole seconds; library boundaries
also accept fractional `int`/`float` seconds, excluding booleans and nonfinite values. The
portable maximum is `(2**32 - 2) / 1000` seconds, excluding Windows' infinite-wait
sentinel. Invalid values fail before outputs or process launch. Identity probes use a
separate fixed 20-second bound. These limits are not whole-workflow deadlines: process
cleanup may add bounded grace, and forced termination cannot recover descendants that
escape the process group.
