# Accessibility scope and limits

ODFA11y inspects an OpenDocument source and, where supported, its PDF/UA-1 export. Source
semantics, native exporter behavior, PDF validation, fidelity and human acceptance are
separate conclusions. A report with no errors is not an accessibility certificate.

## What each tool establishes

| Layer | Evidence provided | What needs human review |
| --- | --- | --- |
| ODF audit | Package/XML readability, kind, version, metadata and selected semantics for eight families; optional validation of known ODF parts/native MathML against bundled schemas. | Whether structure, names, languages and descriptions convey the intended meaning. |
| ODF remediation | Explicit decisions, per-target outcomes, protected content and no introduced violations detectable where a bundled schema is available. | Whether decisions are correct and the result looks right. |
| LibreOffice export | A PDF produced with requested tagging/PDF/UA-1 options. | Whether the actual exporter produces the required structure. |
| Built-in PDF audit | Metadata, tags, roles, headings, lists, tables, figure alternatives, link/structure correspondence, marked-content ownership and inspected text/graphic presence. | Reading order, visual meaning and checks outside this smoke test. |
| veraPDF | Machine-verifiable PDF/UA-1 rules, with clause/test identifiers for failures. | Human checkpoints and assistive-technology use. |
| Fidelity | Extracted text, URI link targets and, under the policy, page geometry/rendered ink. | Intended layout changes and the publication's reading experience. |

## Document families

Kinds are recognized by declared media type, independent of filename extension. Common
checks apply to packaged and flat layouts; a family-specific content model still has to
be valid. Semantic audits and explicit decisions exist for all eight families.

| Family | Explicit decisions and audit scope | Native PDF boundary |
| --- | --- | --- |
| Text | Headings, both table-header axes, graphic alternatives/roles, link descriptions, address linkification, inert spacers and spacing; contextual source audits. | Writer export, PDF checks, veraPDF and fidelity; see measured limits below. |
| Spreadsheet | Sheet names, eligible graphic alternatives/roles and supplied link descriptions; names, data-sheet headers/merges, links, trailing empty sheets and hidden content audited. | Calc export; table-header and validator limitations remain gates. |
| Presentation / Drawing | Page descriptions, eligible graphic alternatives/roles, supplied link descriptions and complete explicit shape navigation. Notes, hidden content and relationships need review. | Separate Impress/Draw filters and the PDF/validation/fidelity gates. |
| Formula | Native MathML expression audit, spoken alternative and language. | Math export lacks required tagging and fails PDF assurance. |
| Chart | Title/description metadata, series/local-range consistency and labels. | Source assurance only; no native PDF filter. |
| Image | Frame/payload integrity, supplied alternatives/roles and external/active declarations. ODF deprecates image media types. | Source assurance only; no conversion to another family. |
| Database | Declared connection/privacy/script properties and supplied object descriptions. | Source assurance only; connections, SQL and macros are never executed. |

A missing native stage is `not-applicable` under source-oriented profiles; production
requires PDF validation and fails that boundary. Source success does not certify opaque
embedded content or database storage. See [configuration](PLAN.md) and
[assurance profiles](WORKFLOW.md#5-or-do-it-all-with-evidence).

### Spreadsheets

`SHEET` checks detect empty/default sheet names, headers and merges on data-like sheets,
undescribed eligible graphics (including vector shapes), raw-address links or missing
source purpose, trailing empty sheets and hidden sheets/rows/columns. They do not assess
whether descriptions are good or validate formula results, chart data or conditional
formatting semantics. Formula declarations are inspected separately for
[native dependencies](#formula-declarations), without evaluation.

Source operations rename unreferenced sheets, set graphic alternatives/roles and set
`office:title` link descriptions. Header rows, merges, visible link labels and hidden
content are not rewritten. See [sheet renaming](PLAN.md#registered-decisions).

### Spreadsheet PDF exports

Calc uses `calc_pdf_Export`. The tested table export on LibreOffice 26.8.0.3 and veraPDF
1.30.3 has tagged cells without `TH` cells (`PDF015`) and inconsistent table-column counts
(veraPDF 7.2-43). Production rejects the header warning before veraPDF; integration tests
require that specific failure and reject unrelated failures.

Calc's default printed header includes the sheet name. A rename can therefore fail text
fidelity (`FID003`); edit/remove the header in Calc first or remediate and review the
printed result. Failed gates leave later stages skipped. Successful tests of correct
rejection do not establish an accessible export.

Target-language ordinals require a separate reviewed plan from address linkification,
spacer removal and table-header changes. Those edits can move physical targets, including
identical links whose content fingerprints cannot distinguish a shifted ordinal.

## Writer table headers

Explicit row/column header decisions establish source semantics separately from PDF
roles. The native Writer header-column test produces valid source markup but no PDF `TH`
cells: `PDF015` remains and production fails the PDF audit. veraPDF alone accepts that
case, so its pass does not establish the missing header relationships. No PDF rewrite or
warning exemption hides this boundary.

## Link descriptions

LibreOffice **26.8 or newer** is required; unidentified versions refuse before conversion.
Source link purpose uses visible labels, graphic alternatives or native `office:title`.
`office:name` is a target name and alone does not establish purpose. Supplied descriptions
set `office:title` and preserve Names and incoming references.

`odfa11y doctor` exports a synthetic `office:title` link and reports
`pdfua_link_descriptions: supported | unsupported`. Text pipeline export runs the probe
once and records it under `toolchain.LibreOffice` in `run.json`; probe files are excluded.
A failed probe execution fails export. The verdict measures that field, not all authored
links and never waives document-level PDF checks.

LibreOffice 26.8.1.1 ignores `office:title` in the tested PDF link-description case: the
supplied-description and missing-title controls both retain `PDF019`/veraPDF failures.
Existing meaningful Writer Names can affect export, but changing them can break targets
and is outside automatic remediation. See the [reproduction](../tests/reproductions/README.md)
and [LibreOffice bug 161583](https://bugs.documentfoundation.org/show_bug.cgi?id=161583#c17).

The Writer internal-bookmark fixture has a real destination and readable source label,
but its exported annotation lacks a description (`PDF019`, veraPDF 7.18.1-2/7.18.5-2).
The broken-target control triggers built-in `PDF017` even though veraPDF accepts it.
Source relationships, PDF checks and human review remain separate gates.

## Graphic roles

Roles resolve from ODF defaults, common/automatic styles, legal inheritance and ordered
class overlays. An explicit role uses ODF 1.4 `draw:decorative` on
`style:graphic-properties`. Each role change derives an isolated style from an established
explicit context; unsupported or ambiguous contexts report `GRAPHIC001` and refuse edits.
See [role decisions](PLAN.md#registered-decisions).

A decorative role removes only the missing-alternative requirement. It never hides invalid
payloads, external resources, scripts, interactivity or incomplete page navigation. Group
roles require review and do not suppress child alternatives. Preserved authored alternatives
on decorative objects produce `GRAPHIC002`. An all-decorative image cannot establish
meaningful PDF content.

On LibreOffice 26.8.1.1, a tested standard decorative property still exports an undescribed
Figure: `PDF007` and veraPDF failures remain, even when established visual styles preserve
pixels, text and links. Source role correctness does not establish PDF artifact behavior;
production retains the PDF failures.

## Language

Document-language decisions preserve well-formed BCP 47 tags in source metadata and all
three supported default script channels, retaining authored content overrides. No language
registry lookup, alias rewriting or inferred override is performed.

LibreOffice 26.8.1.1 reload preserves tested tags including `sr-Latn-RS`, `es-419`,
`de-1996`, `en-u-ca-buddhist` and private use. It aliases `zh-Hant-TW` to `zh-TW`,
`i-klingon` to `tlh`, and `zh-cmn-Hans-CN` to `cmn-Hans-CN`. Exact native tag retention is
not assured for these cases; inspect the exported PDF language separately.

## ODF schema validation

Unmodified OASIS ODF 1.3/1.4 Relax NG schemas ship with source URLs/digests. Validation is
offline. `audit --schema` validates recognized ODF XML parts against the declared version,
not every arbitrary package member. Unsupported versions report `SCHEMA002`. Native formula
expressions additionally use the normative bundled W3C MathML 3 grammar.

Producer documents can violate strict schemas, so `SCHEMA001` is a warning. Where a bundled
schema is available, remediation's *differential* gate rejects violations absent from the source. It identifies a violation
by message and failing-element fingerprint (tag, attributes, parent and neighboring tags),
not position: fixing one cannot hide an equal violation introduced elsewhere. libxml2
reports only the first failing content-model error; another error within that already
failing element can be invisible. Unlocated errors compare by count and are reported as
unlocated. Thus a passing gate means **no introduced violations detected**, not ODF conformance.
`document.odf_version` relabels a document; it does not convert unsupported markup.

## Preservation boundaries

Remediation never invents alternatives, heading levels or header choices. Explicit heading
levels can repair a reviewed hierarchy; merged cells are not split and typed numbering is
not removed. Heuristics need inspection in context.

Only edited members are reserialized. Unchanged members and protected XML facts—including
foreign markup, comments, processing instructions, anchors, fields, geometry, references,
payloads and unrelated styles—must remain. Text guards compare ordered normalized words,
logical grids and operation-specific XML facts; spaces/tabs/breaks retain word boundaries.
Only effects permitted for the operation normalize for that check. Other families protect
values/formulas, shapes/navigation, MathML, chart data and database bindings/settings;
opaque payloads have separate guards. These are not render comparisons; use
[fidelity](FIDELITY.md) and human review.

- Declared signatures (`PKG008`) are unverified: no cryptographic, reference or trust
  validation. Every guarded remediation, including dry runs and no-op plans, refuses a
  signed package. Original export makes no signature claim; exported PDF/evidence does
  not inherit a source signature.
- Manifest encryption (`PKG009`), duplicate ZIP names (`PKG006`) and unsafe paths (`PKG007`)
  prevent a complete inspection view. Planning, remediation and guarded native work refuse
  before selecting body XML. Malformed manifests are never assumed unsigned/unencrypted.
- Tracked changes permit only title/description metadata edits. Language/version/other
  edits refuse. Main outline, spacing and spacer removal exclude notes, text boxes,
  annotations/revisions and hidden/conditional branches. Graphics, links, tables and
  address linkification include eligible current notes/text boxes with qualified locations,
  excluding annotation/revision/conditional branches. `REVISION001`/`HIDDEN001` retain review needs.

Writer 26.8.1.1 exported tracked deleted words in the structure fixture's current view,
while excluding its hidden section. Source inspection retains revision/visibility review;
it does not accept changes or predict which tracked text will be painted. Inspect the
actual PDF and review the document in Writer.

## Native document context and declared dependencies

Guarded export/comparison/pipeline inspect known declarations without fetching resources.
`NATIVE001` marks external, unresolved, wrongly addressed or unestablished rendering/execution
contexts; guarded native work refuses them. Inline data and exact package file/subdocument
addresses can pass preflight, but presence never proves decoding or native loading.
`NATIVE002` marks filename/path-sensitive fields: captured pipeline export refuses them,
while direct export/comparison of original inputs can retain their logical identity.
Source-only `inspect` and preservation remain available. See
[evidence capture](EVIDENCE.md#source-capture) for private copies and stable directories.

The authoritative policy is [content/export_context.py](../src/odfa11y/native/export_context.py).
It covers content/styles/meta, reachable embedded ODF content/styles, auto-reload documents,
unused fill/bullet images, chart symbols, SVG definitions/fonts and form image data.
File targets require an exact non-directory member; decoded separators remain meaningful.
`draw:object` can address a separate file or a folder containing `content.xml`; OLE needs a
file or inline data. Chart self-data `.` is contextual; parent-data `..`, including its
omitted-attribute default, is unestablished. Flat files cannot resolve package members.
Explicit XML rendering bases are unestablished.

Ordinary text/drawing/image-map navigation, template provenance, operated form links and
submission are distinct from automatically loaded image data. Presentation `show` events
are navigation; `execute` events are unestablished execution. Child sounds follow media
file rules. Applet code/base/archive, script/application execution and nonempty form/table/
text database, data-service or DDE bindings remain unestablished even with cached values;
empty named bindings identify no concrete dependency. This classification does not claim
that every declaration runs or fetches.

Opaque/unreachable embedded internals, dynamic importer behavior and inline execution are
outside established inspection. The guard is not an offline/confidential sandbox. Use
caller-controlled native process isolation. The [resource probe](../tools/probe_native_resources.py)
retains PDFs, decoded-pixel controls, options and tool identities for supported-runtime
experiments; observations on one runtime/OS do not establish other combinations.

Core `export_document`, `compare_documents` and pipeline stages own these guards. Raw
`native.export.export_pdfua()` requires caller-owned resource/protection policy and native isolation;
see [API ownership](API.md).

## Formula declarations

Native preflight classifies `style:condition`, `table:condition`, `table:expression`,
`table:formula`, `text:formula`, named expressions/ranges and base/source addresses,
including reachable embedded ODF content/styles. It does not evaluate formulas or trust
cached results. Standard OpenFormula prefixes/aliases and unprefixed expressions are
classified equivalently.

The lexical subset includes literals, ordinary operators/nested calls, bracketed local
cell/range references and scoped simple names. Names are case-insensitive; missing,
ambiguous or cyclic declarations refuse. Unsupported condition grammars such as
`cell-content()`, unknown functions/namespaces and dynamic `INDIRECT` references refuse.
Explicit external references and `DDE` remain loading limitations even in apparently
unreachable branches. `HYPERLINK` is navigation, with its arguments still inspected;
function-like words in strings are inert.

`CELL("FILENAME")` and `INFO("directory")` depend on original identity and refuse captured
pipeline export. Other supported literal CELL/INFO queries classify normally; dynamic or
unsupported queries refuse. The ODF 1.4 Part 4 function/query table is bundled with its
[source and digest](../src/odfa11y/native/formula_data/functions.toml); runtime processing
does not download it.

Each expression is bounded to 32,768 characters, 4,096 lexical tokens and depth 64.
Named dependencies are traversed iteratively with expansion/work limit 4,096 and depth 64;
inspection permits 100,000 declarations per tree and 64 embedded directories, within
package/XML budgets. Exhaustion is incomplete-context refusal. Reports use `NATIVE001`/
`NATIVE002` with declaration/origin/incomplete counts, excluding formula literals/credentials.

## Native execution limits

Work timeouts are finite, positive and per invocation. CLI/core options, `audit_document`
and `check_pdfua` default to 120 seconds; direct `validate_pdfua` defaults to 180.
The selected work timeout applies to LibreOffice exports/capability probes and veraPDF.
Identity probes have a separate fixed 20-second bound.

CLI `--timeout` accepts whole seconds; library boundaries accept fractional `int`/`float`
seconds, excluding booleans and nonfinite values. Maximum: `(2**32 - 2) / 1000` seconds,
excluding the Windows infinite-wait sentinel. Invalid values fail before outputs/launch.
These are not workflow deadlines; cleanup adds bounded grace and cannot recover descendants
that escape process groups. Signal/forced-termination limits are described in [Batch](BATCH.md).

## Threat model

Inputs are untrusted ZIP, XML and PDF. Packages permit at most 10,000 members and 256 MiB
declared uncompressed content; flat XML permits 256 MiB. Packages are read without
extraction; unsafe member names refuse. PDFs permit 256 MiB, 5,000 pages and 500,000
structure elements. XML parsing disables entity resolution/network access.

PDF audit resolves role maps, Link `/OBJR` annotation/page correspondence and page/Form
MCID ownership. Invoked Forms retain resource scopes and stream identities. Shared elements
expand once, incoming ownership edges remain checked, and active-path cycles are bounded.
A text-free document needs described inspected graphical operations; structure declarations
alone cannot establish content. Pixel visibility and correct artifact/reading order remain
outside this test.

Raw inline-image dimensions establish sample boundaries. Filtered inline images/unsupported
inline color spaces and whole-object Form `/StructParent` ownership produce explicit failed
inspection. Malformed decoding, recursion/cycles and exceeded budgets produce `PDF000` or
controlled comparison failure. Unique decoded content and repeated invocation work each have
64 MiB budgets; content arrays permit 10,000 streams, with 5,000 Form invocations and depth
50. Supported decoder controls limit outputs before decoding; final-byte accounting also
checks cached/other data. These do not bound peak memory or render allocations.

Guarded LibreOffice exports use private profiles. Native invocations use argument lists,
bounded captured output and timeouts;
timeouts kill the process tree where the OS permits (Windows uses `taskkill`). Publication
is atomic. Evidence diagnostics redact paths, but payloads can contain private content.
No control here sandboxes LibreOffice, Java/veraPDF, pdfium or other importers or imposes
portable CPU/memory/network isolation. Process untrusted inputs in an isolated environment
with OS resource limits.

## Spacer removal

`remove_empty_spacers` is opt-in. It removes only inert empty main-body paragraphs without
protected graphics/bookmarks/tabs/breaks, table/text-box/annotation/list ancestry or
page/master-page semantics. XML identities, RDF metadata, conditional/class style
references, unrecognized attributes, comments and processing instructions also prevent
removal. The text guard permits exactly the counted removals. Layout usually moves;
review diffs and choose `fidelity.pagination = "may-change"` only when intended.

## Human acceptance

Before distribution, review:

- **Headings:** actual hierarchy and navigation.
- **Alt text (`alt-text`):** meaning in context.
- **Reading order (`reading-order`):** columns, floating frames, sections, notes, tables and spreadsheet order.
- **Lists (`lists`):** intended grouping, nesting and continued numbering.
- **Language (`language`):** applicable western, Asian and complex channels match the wording.
- **Hidden content (`hidden-content`):** revision history and conditional branches preserve intended meaning.
- **Table headers (`table-headers`):** correct data relationships, including spreadsheet header cells.
- **Sheet names and hidden content:** clear names and no inaccessible required information.
- **Link purpose (`link-purpose`):** understandable destinations in context.
- **Colour:** contrast and alternatives for information conveyed by colour.
- **Layout:** typography, pagination, appearance and assistive-technology behavior.

`REVIEW.md` in the [evidence bundle](EVIDENCE.md) carries the family's checklist.
Non-empty alternatives and tags alone do not establish usability.

## Standards and tool references

- [ODF 1.4 specification](https://docs.oasis-open.org/office/OpenDocument/v1.4/) and [schemas](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/schemas/).
- [LibreOffice PDF/UA guidance](https://help.libreoffice.org/latest/en-US/text/shared/01/ref_pdf_export_universal_accessibility.html) and [PDF options](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html).
- [veraPDF](https://docs.verapdf.org/), [pypdf](https://pypdf.readthedocs.io/en/stable/) and [pypdfium2](https://pypdfium2.readthedocs.io/).
