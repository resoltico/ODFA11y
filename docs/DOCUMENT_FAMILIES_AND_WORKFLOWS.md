# Document families and workflow design

## Scope and constraints

This change covers #6 and every remaining implementation issue: heading levels (#20),
header columns (#21), batch execution (#22), SARIF (#23), presentation (#25), drawing
(#26), formula (#27), chart/image (#28), and database (#29). Completion includes real
application fixtures, configuration, preservation, reporting, privacy, distribution
contents, platform CI and release outcomes. A family adapter alone is not completion.

LibreOffice 26.8 is the hard runtime minimum. There are no old-runtime branches,
compatibility aliases, alternate plan formats or migration shims. Published history and
fixture provenance remain factual records. Supporting a current producer's actual media
type is not an excuse to normalize its data into another family.

Audits never execute document macros, database queries or external-resource fetches.
Remediation never invents descriptions, semantic levels, header choices or reading order.
A successful source edit does not imply a conforming PDF, and unsupported stages must be
explicit. Existing error severity, schema regression protection and privacy guarantees
remain requirements through any refactor.

## Architecture decision

Retain the family registry and the generic orchestration pipeline. Replace duplicated
ODF vocabulary mechanisms with a shared `content` package between the adapter contract
and concrete families. It owns structural primitives for text extraction, graphic
identity/descriptions, language styles and logical table grids. It imports no family and
contains no family-specific audit rules or export selection. Families still own:

- semantic applicability and rules;
- explicit operation binding and configuration tables;
- protected-content snapshots and allowed postconditions;
- review items and native export capability.

The alternative of independent copies in eight families is rejected because it multiplies
already observed binary-text, fingerprint, language and table-grid defects. A universal
family with conditional rule prefixes is rejected because it merges different contracts.
A general plug-in framework or mutable intermediate document model is unnecessary: the
existing parsed ODF document remains the edited object.

Update the boundary rules and policy checker to distinguish shared ODF vocabulary from
family meaning. A family cannot import another family; core orchestration cannot select
family XML directly. Shared graphics code does not become a place for page-, chart- or
cell-specific decisions. Public names describe one responsibility; no old class or config
name is retained as an alias when the reviewed change replaces it.

## Explicit text decisions

### Heading levels

`SetHeadingLevels` addresses a logical heading target and requires an explicit level
1–10. Targets use XML identity when present or the report's heading ordinal. A reviewed
content fingerprint is required for an ordinal target. A fingerprint excludes the changed outline level but includes the text and
structural identity. Every target and value is checked before any edit. Unknown,
ambiguous, stale or invalid targets fail without publication. Only `text:outline-level`
changes; words, styles, links and graphics do not. A repeated plan is unchanged.

Configuration, templates and findings expose the same target identity. Verify real
Writer reload and PDF heading roles, including skipped levels, nested inline content,
duplicate text and stale plans.

### Table headers

Use one table-header operation with optional explicit leading row and column counts.
The logical grid understands repetition, row/column groups, spans and covered cells.
Never silently treat physical XML element counts as logical row/column counts. Split a
repeat only when a requested boundary needs it; preserve total counts, cell payloads,
formula/value attributes and ordering. A span crossing a requested header boundary is
rejected rather than guessed. All tables are resolved and validated before edits.

The real Writer experiment produced valid ODF header-column markup but no PDF `TH`
cells. Therefore verify source header semantics and exported structure separately; do
not claim this source operation fixes the exporter. Production gates continue to reject
missing semantic headers. No PDF mutation is introduced to hide this exporter limit. The source operation, native
PDF result and strict-gate rejection are separate tested acceptance properties.

## Family contracts

| Family | Semantic audit and explicit edits | Protected content | Export boundary |
| --- | --- | --- | --- |
| Text | Heading levels, both header axes, existing text decisions | Ordered words, references, graphics, embedded payloads | Writer; named hyperlinks and real table/heading checks |
| Spreadsheet | Existing sheet and object decisions, shared grid correctness | Cell positions, values, formulas, references, binary objects | Calc; retain the known table warning/validator failure |
| Presentation | Page descriptions, title presence, graphic descriptions, explicit complete navigation order, notes/links/hidden content | Page order, shape identity, visible words, geometry, payloads and links | Native Impress filter, verified with a real authored fixture |
| Drawing | Page descriptions, graphic descriptions, explicit complete navigation order and meaningful text | Page/shape identity, words, geometry, payloads and links | Native Draw filter, verified independently of Impress |
| Formula | MathML structure/validation, explicit spoken alternative | Mathematical expression and StarMath annotation | Native Math filter; PDF diagnostics remain honest about missing tagging |
| Chart | Labels, titles/descriptions, data-range/series consistency and an explicit chart description | Chart type, series, numeric data, labels and embedded payloads | Native-authored embedded chart parts form the chart source fixture; standalone PDF export is not assumed |
| Image | Graphic identity, alternative text, external resource and payload integrity | Image bytes, dimensions, references and visible labels | No Draw conversion as an image compatibility path; expose actual native capability |
| Database | Connection/privacy properties, schema/query/form/control descriptions and references | Embedded database bytes, SQL, connection settings and form bindings | Base was authored and schema-validated through the current native service; never connect or render arbitrary inputs |

Page navigation order must contain every addressed top-level shape exactly once and use
existing unique identities. Invalid, partial or stale lists fail. Description operations
edit only the standard title/description metadata, not visible text. Formula alternatives
must not rewrite the expression. Chart edits must not change data. Database descriptions
must not execute SQL, change credentials, rewrite connections or alter embedded storage.

Real fixtures are invented documents authored by the required current LibreOffice. The
older Writer corpus remains a useful input corpus, not an old-runtime execution lane.
Do not label source-only checks as PDF conformance. Unsupported native exports are
`not-applicable` in source-oriented profiles and fail a profile that requires PDF proof.
That is a completed, stated assurance boundary, not a silent family pass.

## Preservation and adjacent correctness

Extend family snapshots to include the content they actually protect: text, formula/value
attributes, references, shape geometry, mathematical expressions, chart data and database
bindings. Exclude only the fields that the declared operations can legitimately change.
Preserve every opaque package payload and flat embedded binary payload. Language and
alternative-text changes must not be counted as visible wording.

Review header-row preflight, direct-Python argument validation, grouped/repeated table
handling and fingerprint stability together with the column change. The existing
operation can mutate an earlier table before a later target fails; publication is atomic,
but operation preflight must match its documented contract too.

Review current producer media types, schema selection, namespace handling, encrypted
inputs, external links, credentials and missing content as part of each family. Error
messages and evidence must not disclose connection credentials or local locations.

## Batch orchestration

Use a strict TOML batch manifest containing explicit entries with an ID, source and plan.
IDs are safe single-directory names and unique under case folding. Paths resolve relative
to the manifest. There are no implicit globs, family guessing, parallel workers or hidden
plan selection. Reuse the single-document loader and pipeline for each entry.

Before running, validate the manifest, destination confinement and global collisions.
Per-document unreadable sources, invalid plans and failed gates produce item failures;
other items continue. The summary records IDs, relative evidence locations, statuses,
failed stages and aggregate exit status (execution errors dominate audit errors, which
dominate strict warnings). Do not expose source/config absolute paths in the summary.

Create the confined batch root after global preflight, with an initial running summary.
Each item bundle is published atomically; summary updates replace one file atomically.
The batch summary explicitly distinguishes
complete, failed and interrupted execution, preserving completed evidence and identifying
unrun entries after interruption. A partial run must never look complete. Test symlinks,
hardlinks, case collisions, occupied outputs, mixed results and interruption at a real
process boundary.

## SARIF reporting

Emit standard SARIF 2.1.0 from registered findings. Preserve rule IDs, severity, remedies
and logical ODF locations. Logical paths are not invented physical line numbers. Package
members are diagnostic metadata, not separate user source files. Equivalent package and
flat documents retain equivalent logical locations.

Artifact mapping uses an explicit source root and root-relative URI-encoded paths.
Reject artifacts outside that root and distinguish identical basenames in different
in-root directories. Never serialize the local root, host username, absolute source path
or raw credential values. Reporting must consume authoritative source identity rather
than parsing a comparison's display label as a filename. Add a non-serialized `sources: tuple[Path, ...]` to `Report`: source audits carry one
artifact; comparisons carry candidate then original. SARIF derives its artifact table
from those references. Display labels are not parsed or used as identity. JSON/evidence
continue to contain safe labels rather than physical source paths.

Validate generated output with the independent OASIS JSON schema, including rule-index
references, locations, URI escaping, global findings and multi-artifact runs. SARIF is a
report format, not a GitHub upload feature; no token or external publication is implied.

## Design QA and delivery conditions

A separate challenge pass follows this design and precedes production implementation.
It must try to disprove exporter capabilities and preservation assumptions with current
LibreOffice, inspect OASIS/W3C contracts, and exercise malformed/ambiguous inputs. Resolve
findings here rather than accepting TODOs as completion.

The implementation follows reviewed dependencies: shared primitives and invariants;
text operations; family contracts and real fixtures; batch/reporting; final integration,
privacy and packaging. Every issue includes its in-scope downstream work. Required gates
remain policy, lint, formatting, types, boundaries, coverage, real integration on Linux,
macOS and Windows, wheel/source-archive checks, dependency/workflow/security checks and
release provenance. New schema inputs carry source, license and integrity evidence.

## Separate design QA findings and resolutions

The challenge pass used current LibreOffice 26.8.0.3 and native application services in
an isolated profile; it did not alter production code or a user profile.

1. **Header columns:** two explicit columns with the first marked as a header remain
   ODF-schema valid. Writer exports no `TH` and the built-in audit emits `PDF015`;
   veraPDF alone does not reject this omission. Require source correctness and explicit
   strict-gate rejection; do not equate a validator pass with header semantics.
2. **Formula:** the native Math service saved an `.odf` with a MathML root and a StarMath
   annotation. `math_pdf_Export` works but produces an untagged PDF. Validate MathML with
   the normative W3C grammar and preserve the expression/annotation; keep PDF failures.
3. **Base:** the native database service saved a schema-valid `.odb` using the standard
   Base media type. Source-only assurance needs no query execution. Real fixtures include
   only invented local data; external connection strings and credential diagnostics must
   be tested without connecting or echoing their values.
4. **Chart:** direct native standalone storage and factory loading failed. A Calc-authored
   chart with an internal data provider supplies real chart content and local-table values.
   Extract only native-authored chart parts into a chart container for the corpus; no
   user document is converted between families. Do not invent a chart PDF filter.
5. **Image:** an empty `office:image` is invalid, but ODF 1.3/1.4 explicitly allow one
   `draw:frame` as its body. The existing synthetic fixture is wrong, not evidence that
   the standard excludes the family. Use a valid frame and real graphic payload; test the
   actual native loader rejection and expose source-only assurance without a Draw shim.
6. **Target identity:** unescaped names can contain location delimiters. Standardize named
   logical selectors as `[name=<percent-encoded>]` and XML identities as `[id=...]`, with
   ordinals remaining `[N]`. Update all affected findings/templates together and version
   the report contract; do not retain ambiguous old selector spellings.
7. **Drift and postconditions:** table fingerprints currently inspect only the first row;
   graphic fingerprints omit actual image bytes. Include protected payload/data facts,
   while excluding mutable accessibility metadata. A shared plan must not invalidate its
   own later fingerprints or accumulate changes on a second run.
8. **Reporting:** a human comparison subject is not a source path. Internal source
   references fix that defect without leaking absolute paths into serialized reports.
   Root confinement must check resolved symlinks as well as lexical paths. OASIS's actual
   SARIF schema declares draft-07, so use that dialect rather than a guessed validator.
9. **Batch:** publication must preserve completed failure evidence on interruption and
   identify pending items. Global ambiguity aborts before work; per-item failures continue.
   A serial runner avoids speculative concurrency and mutable shared-state hazards.

The reviewed implementation is a hard API/configuration/report evolution. Replace the
row-only table decision with one structured `TableHeaders(rows, columns, fingerprint)`
and `MarkTableHeaders`; each entry is a table object, not an integer shorthand. Shared
`GraphicDescription` and protected-content helpers replace duplicated metadata types and
mechanisms. No deprecated import, TOML spelling or serialized location format is accepted
as a migration path. Keep legitimate published records and fixture provenance.

Production implementation may now proceed against these contracts. A new observation
that contradicts them reopens the relevant design/QA decision before more code is added.

Implementation challenge refinements: header wrappers must not change reviewed graphic
positions. Repeat cuts that would duplicate headings, frames or XML/drawing identities
are rejected before mutation. Protected logical table data ignores generated style names;
reviewed target fingerprints retain them. Spreadsheet postconditions protect full sheet
structure, not just displayed strings. The Base adapter accepts the standard `base` media
type; retired `database` and `sun.xml.base` producer aliases are rejected.

Further implementation QA found two boundary defects. Copying an XML subtree drops
inherited namespace declarations used only in attribute values: two identical formula
strings with different `of` bindings previously produced one digest. Protected XML must
capture those bindings from the original tree, then canonicalize structure with precisely
declared editable root attributes omitted. Tests cover inherited and locally declared
bindings, alongside harmless metadata namespace additions.

A real Draw export containing only one described illustration passes veraPDF but the
built-in `PDF010` check rejects it solely because it has no extractable text. That check
must require readable text **or a reachable described Figure**, keeping errors for missing
tagging, missing alternatives and blank/unreadable output. Verify an independent compliant
native positive case and undescribed/empty negative cases; do not suppress the finding.

Native Base QA produced a schema-valid standard ODF 1.4 database with invented embedded
Firebird data and no metadata/styles parts. Metadata remediation must create the standard
optional metadata part when explicitly requested, using the declared supported version and
adding one manifest entry. Preflight conflicting/duplicate manifest declarations before any
mutation; never overwrite a resource. Apply the same standard operation to package families
and retain flat metadata creation. This is ordinary part creation, not a compatibility shim.
Embedded database bytes, settings, connections, SQL and bindings remain protected; source
assurance never opens the connection. A separate producer-output case containing queries
has native schema defects and remains a negative/non-regression fixture rather than a false
clean baseline.

Normative chart-model inspection rejects another proposed shortcut: `chart:chart` has
visible chart-title elements but no `svg:desc` slot. A standalone chart's explicit
nonvisual alternative is its document description, through the existing `[document]`
operation. Reuse that contract instead of inventing an invalid chart-body field or a
second spelling for metadata. Chart audits still check series, local data ranges and labels;
all body data, types, values and references remain protected. No standalone native export
filter is introduced. Native formula content is a packaged MathML root; flat office-body
formula wrappers are not an ODF content model and are rejected, not normalized.

Separate implementation QA found additional counterexamples and revised the affected
contracts before building the fixes: unresolved SVG XML content fails inspection, while
active/external SVG declarations require review; empty MathML tokens/containers do not
establish expression presence; cached chart category/value cardinalities and value types
need consistency checks without expanding repeats. Base fingerprints omit precisely all
editable descendant descriptions so a parent/child plan remains idempotent; flat Base
protects its settings subtree rather than treating the whole flat document as settings.
SQL and settings mutation controls still reject publication. SARIF source confinement
preflights before exports or diff outputs, and execution diagnostics stay private.

The app version now has one declared authority, `[project].version` in `pyproject.toml`.
Runtime reporting derives installed metadata. Release validation independently reads the
project declaration, and isolated-wheel QA compares all three values; stale installed
metadata cannot authorize a tag. Published version records remain historical outcomes.

MathML presence QA preserves legitimate empty collection constructors and quoted empty
strings, as well as explicitly defined content symbols. It rejects empty presentation
placeholders and annotation/phantom-only content. Base recognizes standard server
declarations and reviews nonblank authentication settings without reporting their values;
boolean requirement flags are not credentials. These checks do not inspect opaque storage
for secrets and do not replace the native human review.
