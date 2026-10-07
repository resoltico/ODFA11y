# Accessibility scope and limits

ODFA11y works on an OpenDocument source and its PDF/UA-1 export. The source and the PDF
have separate structures, so both are inspected. A passing report means only that the
implemented checks found no errors; it is not an accessibility certificate.

## What each tool establishes

| Layer | Evidence provided | What still needs review |
| --- | --- | --- |
| ODF audit | Package/XML readability, document kind, version consistency, metadata; for text documents and spreadsheets also selected semantic properties; with `--schema`, validity against the bundled ODF schema. | Whether headings, table headers, sheet names, links and descriptions convey the intended meaning. |
| ODF remediation | Explicit, typed changes with per-target outcomes; unchanged content; no new ODF schema violations. | Whether the choices were right, and the visual result. |
| LibreOffice export | A PDF produced with the requested PDF/UA and tagging options. | Whether this exporter and version produced correct accessible structure. |
| Built-in PDF audit | Metadata, tagging markers, structure roles, heading sequence, list/table shape, figure `/Alt`, that every link annotation has a Link element referring to it on its page and a description (`/Contents` or the element's `/Alt`), that marked content on each page and the structure tree's references to it correspond and that no text is shown outside tagged content and artifacts, extractable text. | Everything veraPDF and a person check; it is a smoke test, not PDF/UA validation. |
| veraPDF | Machine-verifiable PDF/UA-1 rules, each failure with its clause and test number. | Human checkpoints and the actual reading experience. |
| Fidelity comparison | Source and candidate renders agree on pages, text, links and rendered ink under the policy. | Whether an intended change looks right. |

The PDF audit resolves custom roles through `/RoleMap`, visits each structure object once
and parses strictly. Links are checked by correspondence, not by count: each annotation must
be referenced by a Link element's `/OBJR` on the annotation's page. Content is reconciled
the same way: each page's content stream is scanned for marked-content sequences, and the
audit reports MCIDs that no structure element refers to (`PDF020`), references to MCIDs the
page lacks (`PDF021`), MCIDs referred to more than once (`PDF022`) and text shown outside
tagged content and `/Artifact` (`PDF023`). Only content streams of pages are scanned; form
XObjects are not entered, and references into them (`/Stm`) are not judged. Whether tagged
content is in a sensible reading order, or is correctly an artifact, stays with veraPDF and
a person.

Marked-content scanning skips raw inline images using their sample dimensions. Filtered
inline images or unsupported inline color spaces produce `PDF000` rather than guessing
where binary samples end. Form XObjects are not scanned. The decoded-page-content limit
is checked after each stream is decoded; it does not bound the decoder's peak memory.


## Link descriptions depend on the LibreOffice release

PDF/UA requires every link to carry an alternate description. LibreOffice 24.2 derives one
from the link text; newer releases (observed with the macOS package current in 2026) export links without one. ODFA11y reports this as `PDF019` and veraPDF as rules 7.18.1-2
and 7.18.5-2, so a document with hyperlinks can fail `verify` or `production` under one
LibreOffice and pass under another. ODFA11y cannot add a description to the exported PDF, and `PDF019` stays an error: a PDF
whose links lack one is not accessible. Run `odfa11y doctor` to learn in advance which
case applies. It exports a synthetic one-hyperlink document with the installed LibreOffice,
audits the PDF with the built-in audit, and prints `pdfua_link_descriptions: supported`
(no `PDF019`) or `unsupported`. `doctor` exits `0` whenever the check ran, even when the
answer is `unsupported`, and `3` when LibreOffice is missing or its export fails (the
other versions are still printed). The pipeline's evidence records the LibreOffice version
so the difference is explainable, but not this capability.

## Document families

Every ODF kind is recognised from its declared media type, as a package or as flat XML,
and gets the common checks. Semantic audit and remediation exist per family; today text
documents (`.odt`, templates, master and web documents) and spreadsheets (`.ods`, `.ots`,
`.fods`) have them. For any other family the audit says so with `ODF009`, only the common
`[document]` decisions apply, a plan for another family's table is refused, and PDF export,
PDF checks and fidelity comparison are `not-applicable` in the pipeline (the `production`
profile fails instead, because it requires PDF validation). A document of a recognised kind
therefore never receives rules that belong to another family, and silence about a family is
never a pass.

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

- **LibreOffice 24.2.7:** the sampled exports tag page headers, footers and pictures but
  leave cell text untagged. `PDF023` rejects that text, independently confirmed by
  veraPDF PDF/UA-1 clause 7.1, test 3. Links also lacked `Link` elements (`PDF016`, and
  veraPDF clause 7.18.5, test 1). Heading, list and table rules (`PDF008`, `PDF012`–`PDF015`)
  had no cell structure to inspect; `PDF004` passing did not mean cells were tagged.
- **LibreOffice 26.8.0.3:** the sampled table export has tagged cells but no `TH` cells
  (`PDF015`), and veraPDF reports inconsistent table-column counts (clause 7.2, test 43).
  The `production` profile rejects the table-header warning before reaching veraPDF.
- Metadata, pictures and extractable text remain meaningful diagnostics (`PDF000`–`PDF003`,
  `PDF006`, `PDF007`, `PDF009`, `PDF010`). A person must check the language: the 24.2 sample
  exported `en-US` even when the source declared `de-DE`.
- Fidelity comparisons check pages, text, links and ink. Calc's default header prints the
  sheet name, so a rename changes rendered text (`FID003`). The pipeline may stop earlier
  on an invalid PDF; the standalone `compare` command can still assess the exported pair.
  Change or remove the header in Calc first, or use `remediate` and review the printed result.

These observations use small invented Calc-authored fixtures and veraPDF 1.30.2. They do
not establish that every spreadsheet or LibreOffice release behaves identically. Integration
tests require the observed gate failures and reject unrelated validator failures. No warning
or error is whitelisted in the application. An earlier failed gate leaves downstream stages
`skipped`; a green integration test can prove correct rejection of an invalid export.

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
documents, whose content is MathML, have no schema here and are not validated.
`document.odf_version` relabels the package; the result must still validate for the new
version. A relabelled or untouched document is "no new violations", never "ODF-conformant".

## Preservation boundaries

Remediation never invents alternative text, heading levels or table-header choices. It
does not split merged cells, repair heading hierarchies or remove manually typed
numbering. Table and link heuristics can produce false positives; review the finding in
context.

Only members an operation edits are re-serialized; every other member, and any foreign
markup, comments and processing instructions inside edited ones, is carried over. The text
guard compares, for text documents, the sequence of paragraph and heading strings after
collapsing whitespace and treating non-breaking spaces as spaces (graphic title and
description are excluded); for spreadsheets, the sheets in order and the text and position
of every non-empty cell (sheet names may differ, since renaming them is the operation);
and, for other families, the whole body text. It detects wording changes but is not a byte comparison, a rendering comparison or proof of
unchanged pagination: that is what [fidelity comparison](FIDELITY.md) adds.

## Threat model

Inputs are untrusted ZIP, XML and PDF files. Package input is limited to 10,000 members and
256 MiB of declared uncompressed data, and a flat XML file to 256 MiB, checked before
loading; packages are never extracted, so path traversal does not apply, and the writer
refuses unsafe member names. PDF input is limited to 256 MiB, 5,000 pages and 500,000
structure elements. XML entity resolution and network access are disabled. LibreOffice and
veraPDF are run with argument lists (never a shell), a temporary profile and timeouts, their
output is captured only up to a size limit, and a timed-out run has its whole process tree
killed (on Windows through `taskkill`). Outputs are published atomically, a source is never
overwritten, and evidence never carries local paths or is read through links outside it
(see [Evidence](EVIDENCE.md)).

These controls do not sandbox anything and set no CPU or memory limit (a limit that
LibreOffice or a Java runtime tolerates is not portable). Rendering for fidelity uses
pdfium, native code that parses PDFs, and veraPDF is a Java application; process untrusted
documents in an isolated environment with operating-system resource limits.

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
