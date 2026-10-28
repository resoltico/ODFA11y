# Accessibility scope and limits

Use this guide to interpret a result and decide the remaining native/human work. Source
validity, meaning, exporter behavior, PDF machine checks, fidelity and human acceptance
are separate conclusions. A clean automated report is not an accessibility certificate.

## Document families

| Family | Source decisions and checks | Native PDF boundary |
| --- | --- | --- |
| Text | Headings, lists, references/notes, language, tables, graphics, links, visibility and spacing. | Writer; actual PDF and human gates still apply. |
| Spreadsheet | Sheet names, alternatives/roles, supplied link descriptions; data/header/merge/hidden checks. | Calc; header/validator limitations can block production. |
| Presentation / Drawing | Shared page metadata, graphic decisions and complete navigation order. | Impress/Draw; hidden layers, notes and actual navigation require review. |
| Formula | Supplied spoken alternative and language on packaged native MathML. | Tested Math export lacks required tagging. |
| Chart | Metadata, series/labels and local cached-data/range consistency. | Source assurance only. |
| Image | Frame/payload integrity and supplied alternatives/roles. | Source assurance only; ODF deprecates image media types. |
| Database | Offline connection/privacy and supplied declared-object descriptions. | Source assurance only; no SQL, connection or macro execution. |

Kinds follow declared media types, independently of filename extension. Valid family
representations remain required; an office-body Formula wrapper is not supported.
Source-only profiles can record PDF stages as not-applicable; production fails missing
required PDF assurance. Opaque embedded internals are not certified by source success.

## Writer text structure

List audits check membership, nesting, identities and continuation; typed bullets/numbers
remain review candidates. Counter levels reset at cells/text boxes. Empty/header-only lists
are permitted. There is no typography-based rewrite.

References resolve bookmarks, reference marks, note IDs and internal destinations by their
actual kinds. `office:name` identifies a target, never alternative text. Named ranges may
overlap but must have consistent endpoints in their reading context. Missing/ambiguous
relationships require native editing; no retargeting is inferred.

Effective language resolves paragraph and nested inline styles through named, automatic
and direct formatting, separately for western/Asian/complex channels. Target decisions
create isolated verifiable styles and retain wording/unrelated overrides. No registry
lookup, alias rewriting or language guessing occurs. Native reload can normalize tags:
26.8.1.1 retained tested `sr-Latn-RS`, `es-419`, `de-1996`, `en-u-ca-buddhist` and private use,
but normalized tested Chinese/grandfathered forms. Inspect actual PDF language separately.

Target-language ordinals require a separate reviewed plan from linkification, spacer
removal or table-header edits. Identical objects can otherwise occupy shifted ordinals.
Inherited full language tags that prevent a requested component override explicitly refuse.

## Writer table headers

Declared values/formulas and semantic bands establish source-supported data classification;
short labels or visually numeric text do not. Layout candidates/ambiguous intent require
native review and refuse inferred header edits. Actual grid/coverage/band relationships
replace blanket merge warnings. Valid complex/grouped headers are retained. Complex-grid
inspection is bounded to 100,000 cells; simple repeats remain arithmetic. The leading-band
API cannot rewrite unsupported group-level choices.

Row/column header markup is separate from PDF roles. Tested Writer header-column edits
retain valid source but export no `TH`: built-in `PDF015` blocks strict production although
veraPDF accepts that PDF. Valid merged row headers pass the measured validator case;
that alone does not establish correct human header associations.

## Spreadsheet PDF exports

Calc's measured data export lacks `TH` (`PDF015`) and has inconsistent column counts
(veraPDF 7.2-43). Production retains these failures. A sheet rename can also change its
printed header and fail text fidelity (`FID003`); review/edit that header in Calc first.
Source changes never rewrite cell values/formulas, headers, merges or hidden state.

## Link descriptions

Readable labels, graphic alternatives or `office:title` can establish source purpose.
Supplied descriptions preserve visible text and target names. The measured Writer
`office:title` probe remains unsupported on 26.8.1.1; source success does not clear `PDF019`.
Its internal-bookmark fixture has a real destination/readable label but exported annotation
Contents/Alt is absent (`PDF019`, veraPDF 7.18.1-2/7.18.5-2). Conversely the broken-target
control triggers built-in `PDF017` while veraPDF accepts it. Never rely on one layer alone.

## Graphic roles

Roles resolve legal defaults/common/automatic inheritance and ordered class overlays.
Explicit ODF 1.4 `draw:decorative` changes derive isolated styles; ambiguous contexts refuse.
A role never hides invalid payloads, external resources, scripts or navigation failures.
Groups retain child checks; authored alternatives on decorative objects still need review.
The measured standard decorative property exports an undescribed Figure on 26.8.1.1,
retaining `PDF007`/veraPDF failures. An all-decorative image cannot establish meaningful content.

[Generated capabilities](CAPABILITIES.md) link exact tool identities/probe observations;
[text fixture measurements](verification/0.8.0-text-exports.json) retain narrower results.
Neither implies support for every document or runtime combination.

## ODF schema validation

Unmodified OASIS 1.3/1.4 and W3C MathML 3 grammars ship with notices/provenance. Offline
`audit --schema` validates recognized parts against the declared version, not arbitrary
members. Unsupported versions report `SCHEMA002`; producer violations are `SCHEMA001` warnings.
Remediation compares message/element fingerprints as a multiset, including attributes,
parent and neighboring tags. A fix cannot hide an equal newly located violation.
Unlocated violations compare by count. libxml2 can expose only one error inside an already
failing model: a passing differential gate means no introduced violation was detected,
not complete conformance. `document.odf_version` relabels; it does not convert markup.

## Preservation boundaries

Only permitted effects normalize for protection checks. Wording/order, logical grids,
references, fields, anchors, geometry, comments/processing instructions, foreign XML,
payloads and unrelated styles remain protected. Other families also protect their data,
formulas, navigation, MathML, chart ranges and database bindings. Unchanged members retain
bytes. These checks complement [render fidelity](FIDELITY.md).

Declared signatures are unverified (`PKG008`); all guarded remediation refuses, including
no-op/dry runs. Original export makes no signature claim. Encryption (`PKG009`), duplicate
ZIP names (`PKG006`), unsafe paths (`PKG007`) or malformed manifests block complete access.
Planning/remediation/native work do not select a protected body through those failures.

Tracked changes permit title/description metadata only; language/version/structural edits
refuse. Revision identities and point/range anchors are checked, with unestablished anchors
retaining review. Conditions are not evaluated; cached visibility never authorizes editing
excluded branches. Current notes/text boxes can have qualified targets; annotations,
revision history and hidden/conditional branches stay excluded. Main outline/spacing/spacer
edits have narrower main-flow scope. Spacer removal also excludes lists/tables/fields,
identities/RDF, breaks/page semantics, unknown attributes and non-inert inline content.

Writer 26.8.1.1 painted tracked deleted words in the measured current view while excluding
its hidden section. Inspection neither accepts revisions nor predicts that deleted text
will be absent. Columns, floating frames, sections and notes retain reading-order review;
declared layout alone does not prove native use/order.

## Native document context and declared dependencies

Guarded export/comparison/pipeline classify known declarations without fetching resources.
`NATIVE001` identifies external, unresolved, incorrectly addressed or unestablished loading/
execution context. Inline/exact package files or subdocuments can pass, but presence does
not prove decoding/loading. Captured filename/path fields (`NATIVE002`) refuse; original
export/comparison can retain identity. See [source capture](EVIDENCE.md#source-capture).

The [native policy](../src/odfa11y/native/export_context.py) covers content/styles/meta,
reachable embedded ODF, reloads, fill/bullet images, chart symbols, SVG definitions/fonts,
form images and rendering XML bases. Files require exact non-directory members; object
folders require content.xml, while OLE needs a file/inline data. Chart self-data `.` is
contextual; parent-data `..` is unestablished. Flat documents cannot resolve package resources.

Navigation/template provenance differs from loaded image data. Presentation show events
are navigation; execution/applets/scripts and nonempty form/table/text database, service
or DDE bindings remain unestablished despite cached values. Empty named bindings identify
no concrete dependency. Opaque internals/dynamic importer behavior remain outside inspection.
Raw `native.export.export_pdfua` callers own guard policy/isolation.

## Formula declarations

Preflight inspects formulas, conditions, named ranges/expressions and base/source addresses,
including reachable embedded ODF. It does not evaluate expressions or trust caches. Standard
OpenFormula prefixes/unprefixed forms classify equivalently. The subset includes literals,
ordinary operators/calls, bracketed local references and scoped case-insensitive names.
Missing/ambiguous/cyclic names, unknown functions/namespaces, unsupported condition grammars
and dynamic `INDIRECT` refuse. External references/DDE remain limitations even in unreachable
branches. HYPERLINK is navigation but arguments are inspected; string contents are inert.

`CELL("FILENAME")`/`INFO("directory")` refuse captured export; other supported literal
queries classify normally. [Bundled function/query provenance](../src/odfa11y/native/formula_data/functions.toml)
is offline. Expressions permit 32,768 characters, 4,096 tokens and depth 64; iterative
named work permits 4,096 expansions/depth 64, 100,000 declarations/tree and 64 embedded
directories within package budgets. Exhaustion is explicit incomplete-context refusal.

## Native execution limits

Selected work timeouts default to 120 seconds per invocation; direct `validate_pdfua`
defaults to 180 and identity probes have a separate 20-second bound. CLI accepts whole
seconds; library calls accept fractional finite positive numbers, excluding booleans.
The portable maximum is `(2**32 - 2) / 1000` seconds. Invalid values fail before launch/output.
Timeouts are not workflow deadlines; cleanup adds grace and cannot recover escaped descendants.
See [batch interruption](BATCH.md).

## Threat model

Packages permit 10,000 members/256 MiB declared uncompressed content; flat XML and PDF each
permit 256 MiB. ZIPs are read without extraction; XML disables entities/network access.
PDF permits 5,000 pages/500,000 structure elements. Audit reconciles roles, Link OBJR/page
relationships and page/Form MCID ownership, retaining resource scopes and incoming edges.
Inspected painted graphics are not proof of pixel visibility or correct artifact order.

Unsupported filtered inline-image/color-space boundaries, whole-Form StructParent ownership,
malformed decoding, cycles and exhausted budgets cause explicit incomplete inspection or
`PDF000`/comparison failure. Decoded content and repeated work each have 64 MiB budgets;
arrays permit 10,000 streams, with 5,000 Form invocations/depth 50. Decoder/final-byte checks
do not bound peak memory or raster allocations.

Native tools use argument lists, private profiles, bounded output and process-tree cleanup
where supported (Windows uses taskkill). These controls do not sandbox LibreOffice,
Java/veraPDF, pdfium or importers and do not impose portable CPU/memory/network limits.
Use OS isolation/resource limits for hostile inputs. [Diagnostic redaction](EVIDENCE.md#privacy)
does not make document/PDF/image payloads safe for public sharing.

## Human acceptance

Follow the family's generated `REVIEW.md` before distribution. For text, check **headings**,
**alt-text**, **lists**, **language**, **table-headers**, **link-purpose**, **reading-order**,
**hidden-content**, **colour** and **layout** against actual meaning, navigation and appearance.
Other families add data, forms, page/layer/note, mathematical or database-specific questions.
Nonempty descriptions/tags and validator compliance alone do not establish usability.
