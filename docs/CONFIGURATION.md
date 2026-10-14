# Configuration

One TOML file holds every decision: document metadata, the choices that belong to a
document family, and the fidelity policy. It is never loaded automatically; pass
`--config document.toml` to `remediate`, `pipeline` or `compare`. There are no command-line
flags that duplicate these settings, so the file is the complete, reviewable statement of
what will change. Run `odfa11y template original.odt` to print a commented starter file for
the decisions an audit leaves open.

The file has two common tables, `[document]` and `[fidelity]`, and one table per document
family (`[text]`, `[spreadsheet]`, `[presentation]`, `[drawing]`, `[formula]`, `[image]`, `[database]`); Chart uses only the common `[document]` table. The drawing adapter
serves the standard's graphics family. A family table is read by that
family's adapter and applies only to documents of that family: configuring `[text]` for a
spreadsheet, or `[spreadsheet]` for a text document, is an error that stops the run before
anything is written, never a silently ignored section. Other families expose decisions appropriate to their contracts
when supported (see [Architecture](ARCHITECTURE.md#document-families)).

## Example

Copy this single maintained example, replace the sample values with choices appropriate
to the actual document and delete what you do not need.

```toml
[document]
# odf_version = "1.4"   # relabel the document; omit to keep the declared version
title = "Example report"
description = "Summary of the reporting period"
language = "en-GB"

[text.remediation]
linkify_plain_addresses = true
# Opt in only after reviewing layout and intentional page-break semantics.
remove_empty_spacers = false

[text.table_headers]
# Uncomment only for a real data table named Data with one header row. The fingerprint
# (printed by `odfa11y template`) makes the run fail if the table is no longer the one
# you reviewed.
# Data = { rows = 1, fingerprint = "0123456789abcdef" }

# Uncomment only after identifying the graphic and writing meaningful alt text.
# [text.graphics.Logo]
# title = "Organisation name"
# description = "Description of the information conveyed by the graphic"
# fingerprint = "0123456789abcdef"

# [text.spacing]
# reference_text = "Text of the paragraph whose spacing is the reference"
# target_styles = ["BodyTight"]

# For spreadsheets (.ods, .fods) use the [spreadsheet] table instead of [text]. Sheet
# renames are refused for any sheet a formula, range or link refers to by name.
# [spreadsheet.sheet_names]
# "Sheet1" = "Budget 2026"
#
# [spreadsheet.graphics."Company logo"]
# title = "Organisation name"
# description = "Description of the information conveyed by the picture"
# fingerprint = "0123456789abcdef"

[fidelity]
pagination = "same"
```

A test extracts this block and loads it through the real reader.

## Fields and defaults

| Table/key | Accepted value | When omitted |
| --- | --- | --- |
| `document.odf_version` | `"1.3"` or `"1.4"` (versions with a bundled schema). | The declared version is kept. |
| `document.title` | Nonblank string; stripped before use. | Existing title kept. |
| `document.description` | Nonblank string; stripped before use. | Existing description kept. |
| `document.language` | Well-formed BCP 47 tag, including scripts, numeric regions, variants, extensions, private use and grandfathered syntax; sets metadata and all three default script channels where supported. Named, automatic and direct content overrides are retained. Separators/casing are normalized without registry lookup or alias rewriting. | Existing languages kept. |
| `text.remediation.linkify_plain_addresses` | Boolean. | `false`. |
| `text.remediation.remove_empty_spacers` | Boolean; see [spacer removal](ACCESSIBILITY.md#spacer-removal). | `false`. |
| `text.table_headers.TABLE_NAME` | Structured decision `{ rows = N, columns = M, fingerprint = "…" }`; at least one positive leading logical count. Repeats are counted; an omitted axis stays unchanged. | No change. |
| `text.heading_levels."TARGET"` | `{ level = N, fingerprint = "…" }`, level 1–10. Use the exact logical target from the report. Ordinal targets require a reviewed fingerprint. | No change. |
| `text.graphics.KEY.title`, `.description` | Nonblank string. | Existing text kept. |
| `text.graphics.KEY.fingerprint` | The reviewed identity of the addressed graphic(s); required for explicit roles. | Optional for alternative text. |
| `<family>.graphics.KEY.decorative` | Optional boolean for Text, Spreadsheet, Presentation, Drawing and Image; requires ODF 1.4 and reviewed fingerprint. | Existing role kept. |
| `<family>.links."TARGET"` | `{ description = "…", fingerprint = "…" }` for Text, Spreadsheet, Presentation and Drawing. Both strings must be nonblank. | Existing `office:title` kept. |
| `text.spacing.reference_text` | Text contained in the reference paragraph (required with `[text.spacing]`). | — |
| `text.spacing.target_styles` | Non-empty list of paragraph style names (required with `[text.spacing]`). | — |
| `text.spacing.exact_reference`, `text.spacing.include_headings` | Boolean. | `false`. |
| `spreadsheet.sheet_names."CURRENT"` | The new name of the sheet currently named `CURRENT`: not blank, without `[ ] * ? : / \`, no apostrophe at either end. | Sheet keeps its name. |
| `spreadsheet.graphics.KEY.title`, `.description`, `.fingerprint` | As for `text.graphics`, addressing frames in sheets. | See `text.graphics`. |
| `presentation.pages."PAGE"`, `drawing.pages."PAGE"` | Structured entry with optional string `title`, `description`, `fingerprint`, and `navigation = ["shape-id", …]`. | Existing metadata/order kept. |
| `presentation.graphics.KEY`, `drawing.graphics.KEY` | As for `text.graphics`, including vector shapes. | Existing descriptions kept. |
| `formula.alternative`, `formula.fingerprint` | Nonblank spoken alternative and optional reviewed expression digest. | Native MathML `alttext` kept. |
| `image.graphics.KEY` | As for `text.graphics`, addressing the standalone image frame. | Existing descriptions kept. |
| `database.descriptions."TARGET"` | `{ text = "…", fingerprint = "…" }`, addressing the exact report target. Ordinal targets require the fingerprint. | Existing object descriptions kept. |
| `fidelity.pagination` | `"same"` or `"may-change"`; see [Fidelity](FIDELITY.md). | `"same"`. |
| `fidelity.raster_tolerance` | Finite non-negative number; no upper cap. | `0.15`. |
| `fidelity.ink_threshold` | Integer 0–255. | `200`. |
| `fidelity.dpi` | Positive integer. | `72`. |

Unknown keys, wrong types, non-table sections and non-positive counts are rejected with
the offending key named. TOML booleans are `true`/`false`, not strings. An empty file is
valid and requests no change. Operations run in a fixed order (version, metadata, then the
family's operations: for text, linkify, spacer removal, graphics, heading levels, table headers, spacing; for
spreadsheets, sheet names, then graphics; supplied link descriptions follow the family operations), so a configuration always means the same thing.

Language remediation preserves the requested source tag, without inferring exporter
aliases. Native reload experiments with LibreOffice 26.8.1.1 show that `sr-Latn-RS`, `es-419`,
`de-1996`, `en-u-ca-buddhist` and private-use tags survive across all three default
channels, with authored named-language overrides retained. Native reload also changes
`zh-Hant-TW` to `zh-TW`, `i-klingon` to `tlh`, and `zh-cmn-Hans-CN` to `cmn-Hans-CN`.
Exact native tag preservation for these cases remains an exporter limitation; source
semantics, native behavior and the exported PDF's language require separate review.


## Every selector must match, and mean what you reviewed

A table name, graphic key or spacing reference that matches nothing fails the whole run
and nothing is written; the message lists every miss. Use a table's actual `table:name`
(not its position or caption). Graphic keys match the `draw:frame` name, the complete
image `href`, then the image file name, exactly; quote TOML keys containing dots or
slashes, for example `[text.graphics."Pictures/logo.svg"]`. A table that already has header
rows or columns is *unchanged* when the count agrees; an explicit different count revises the boundary. Spans crossing a chosen boundary and non-leading header bands are rejected.

Selectors are resolved before anything is edited. Two entries that address the same graphic
and set the *same field to different values* both fail; entries that set different fields,
or the same value, combine.

A **fingerprint** binds an entry to the object you reviewed. It is a short digest of the
object's identity and protected facts (a graphic's structural position, dimensions, references
and payload bytes; a table's complete logical data, attributes and grid), excluding the
accessibility metadata the operation edits. If the document has drifted so that the key now addresses something else, the
entry fails with "no longer the object this plan was reviewed against". `odfa11y template`
prints the fingerprint of every object it suggests; leaving it out turns the check off.

Describing a graphic is a judgement about this document's meaning. The presence of a
title or description is only a structural check; do not give every image an arbitrary
description just to make a finding disappear.

## Heading levels

Use the report target, such as `content/heading[2]` or `content/heading[id=section]`,
quoted as the TOML table key. Choose the level; the template never enables a guessed
choice. Every target is resolved before editing. Only `text:outline-level` changes.
The fingerprint ignores that attribute, so repeated application is unchanged, and rejects
changed heading content or an ordinal that now selects a different heading.

## Renaming sheets

`[spreadsheet.sheet_names]` maps a sheet's current name to its new one and nothing else
changes. Every entry is checked before the first edit and any problem fails the run:

- an unknown sheet, or a name shared by two sheets;
- a new name that is blank, contains `[ ] * ? : / \`, starts or ends with an apostrophe, or
  matches another sheet (letter case ignored; a change of case alone is fine);
- a new name that is another entry's current name, or two entries with one new name. Chains
  and swaps are refused, which is also what makes re-applying a plan to its output change
  nothing: an entry whose old name is gone but whose new name exists is *unchanged*;
- **a sheet that anything refers to by name.** ODFA11y does not rewrite references. It
  refuses the rename when any attribute of the document (a formula, a range, a print range,
  a link such as `#Sheet1.A1`) contains the sheet's name followed by a dot, plain or quoted
  as a formula writes it, or is a link to the bare name; and it refuses every rename when the
  document embeds charts or other objects, whose own references to sheets are not inspected.
  Dynamic `INDIRECT`, `ADDRESS` and `HYPERLINK` formulas and embedded scripts also block
  every rename because their sheet references cannot be resolved safely.
  Reference matching includes case variants and URL-escaped names. The test errs towards refusing (a sheet named `Data` is also blocked by a reference to
  `MyData.A1`). Update the references in Calc first, or rename in Calc.

Renaming updates the sheet keys in table view and script-configuration settings, and
the active-sheet selection, in
`settings.xml` or flat XML. A test reloads a renamed document in LibreOffice and exports it. Renaming also changes what Calc's default page header prints, see
[spreadsheet PDF exports](ACCESSIBILITY.md#spreadsheet-pdf-exports).

## Presentation and drawing pages

`[presentation.pages]` and `[drawing.pages]` address exact unique `draw:name` values.
Each page decision sets supplied standard title/description metadata and optionally a
complete navigation list. Navigation uses existing XML/drawing shape identities, includes
every top-level shape exactly once (a group is one entry), and rejects identities duplicated
anywhere in the content document. No identity or reading order is guessed. If identities
are missing, set explicit navigation in the native application first and save the document.
Templates leave every choice commented out.

The existing family `graphics` tables describe frames and eligible vector shapes.
Descriptions are inserted in the standard order appropriate to their element. An empty
native notes placeholder or a generated page thumbnail does not need an invented graphic
alternative. Notes, annotations, hidden slides/layers, group relationships and visual
meaning still need the adapter's human review.

Page metadata is a source semantic decision; it does not create visible heading text or
claim a PDF heading role. Complete native integration independently checks figure
alternatives, PDF/UA validation, fidelity and evidence.

## Graphic roles and link descriptions

`GraphicAlternative` and family `SetGraphicAlternatives` operations accept optional title,
description, decorative role and fingerprint fields. Omitting a field preserves it.
Blank supplied alternatives refuse. `decorative = true` requires an explicit human decision;
it cannot be combined with a supplied title or description, including overlapping selectors.
An existing authored alternative remains and produces `GRAPHIC002` for review. `false`
restores meaningful status and the ordinary alternative requirement. Either explicit role
requires ODF 1.4 and a reviewed fingerprint; use `document.odf_version = "1.4"` in the plan
when relabeling a valid 1.3 source. Existing schema gates still apply.

The role is stored as standard `draw:decorative` on `style:graphic-properties`. Target-specific
automatic styles retain visual properties and legal common-style parents. Ordered class
lists remain; a proven final derivation supplies the requested role. Shared authored styles
and unrelated objects remain intact. Reapplication reuses a proven isolated derivation.
Missing references, ambiguous same-scope styles, inheritance cycles, invalid role values
and mixed graphic/presentation precedence refuse. Absence of optional style declarations
resolves to the standard meaningful default. Text, controls, actions, hyperlink contexts
and explicit group role edits refuse decorative intent. Existing group roles require review
and never suppress child alternatives or payload checks.

`LinkDescription` and family `SetLinkDescriptions` edit only native `office:title` on
eligible `text:a` or `draw:a`. Use the exact target and fingerprint from the report: legal
Draw link IDs are percent encoded as `content/link[id=…]`; other links use one-based
ordinals, with note/text-box context prefixes where applicable. Writer links have no native
XML ID slot. Repeated or ambiguous logical link targets refuse. Hrefs, labels, target Names,
geometry and incoming references are preserved. ODFA11y never derives a description from
a URL or authors `office:name` as an accessibility workaround.

Ordinal link descriptions cannot be combined with address linkification or table-header
operations that can change enumeration. Finish structural editing, regenerate the template,
and review a separate link-description plan. Page, graphic and link metadata decisions
compose and reapply. Source descriptions and roles do not certify PDF export behavior;
see [the measured exporter limitations](ACCESSIBILITY.md#graphic-roles).

## Spacing

`[text.spacing]` copies the effective spacing of the paragraph containing `reference_text`
onto the paragraphs using each target style. It creates a derived style named
`A11ySpacing_<style>_<digest>` instead of rewriting shared styles, and recognises its own
result, so applying it again changes nothing. A style of that name is reused only when it is
provably ODFA11y's own earlier output (an unmodified derivation of the base style that
differs from it only in spacing); anything else of that name is left untouched and the
operation fails, so an author's style is never overwritten or reinterpreted. Use
`odfa11y styles` to choose the styles. Paragraph `text:class-names` overlays and
`text:cond-style-name` references have unestablished precedence here: style inspection reports
`TXT062`, and affected reference or target paragraphs refuse spacing edits before mutation.

## Re-applying a configuration

Every operation reports `applied`, `unchanged` or `failed`. A second run over the result
reports everything `unchanged` and writes identical members. `remediate --dry-run` shows
the outcomes without writing.

## Formula, Chart, Image and Base

Formula decisions edit native MathML `alttext` and language, preserving the expression and
StarMath annotation. The bundled normative MathML 3 grammar validates native expressions;
an invented flat `office:formula` wrapper is rejected. Math's native PDF export currently
lacks required tags, so source success does not establish PDF/UA conformance.

Chart alternatives use `[document].description`, and identifying titles use
`[document].title`. There is no separate chart plan or visible title rewrite. Data, series,
ranges, formulas and labels remain protected. External data providers are reported and
never fetched. Image descriptions use `[image.graphics]`; malformed payloads fail and
active/external SVG declarations need review. Standard image media types remain deprecated.

Base plans use `[database.descriptions."content/query[name=Example]"]` with nonblank
`text` and a reviewed `fingerprint`. Declared objects use standard `db:description` or
form control `form:title`. SQL, bindings, settings and opaque database/form/report bytes
remain protected. Connections, queries and macros are never executed. Chart, Image and
Base have no native PDF export contract; `production` fails at that assurance boundary.

When native packages omit optional `meta.xml`, explicit document metadata creates the
standard part and its manifest entry, using the declared supported ODF version.

## Graphic roles and native link descriptions

The Python decision is `GraphicAlternative` and each graphic-bearing family exposes
`SetGraphicAlternatives`; serialized operation names are `set_graphic_alternatives`.
The previous description names have no aliases. Regenerate templates and reviewed
fingerprints after upgrading: report format 5 distinguishes current body/note/text-box
contexts, excludes history/annotations/conditional branches, and strengthens protected facts.

`<family>.graphics.KEY.decorative` accepts only a boolean: `true` explicitly declares a
noninteractive leaf decorative, `false` restores meaningful status, and omission leaves
its role untouched. Any supplied boolean requires an explicitly selected ODF 1.4 source.
A role decision requires its reviewed fingerprint. New nonblank title/description values
cannot be combined with `true`, including overlapping selectors. Blank supplied text,
text-bearing/action/control contexts, groups and unresolved styles refuse before edits.
Existing authored alternative metadata is retained; a decorative conflict produces a
review warning and fails production strict gates. Target-specific derived styles preserve
visual properties, legal parents and class overlays; repeated decisions do not add styles.
Mixed graphic/presentation precedence remains an explicit unsupported context. A role change
without an established explicit style reference also refuses: introducing a style can change
native implicit placement and wrapping. Fingerprints bind descendant graphical style
dependencies for group, hyperlink and page targets as well as their own content.

`<family>.links."TARGET"` is supported for `text`, `spreadsheet`, `presentation` and
`drawing`. Each entry requires a nonblank `description` and reviewed `fingerprint`.
`SetLinkDescriptions` writes only normative `office:title`, retaining the href, visible
label, child geometry and authored `office:name` target name. Legal draw:a IDs use
percent-encoded `content/link[id=...]`; text:a uses one-based ordinals, with note/text-box
context prefixes where applicable. No XML IDs are invented for text:a.

```text
# [text.links."content/link[1]"]
# description = "Annual report downloads"
# fingerprint = "COPY_FROM_THE_CURRENT_TEMPLATE"
```

An ordinal description plan cannot also linkify addresses or change table headers.
Apply the structural plan first, regenerate the template, review it, and apply the link
plan separately. Page, graphic and link metadata decisions compose without shifting
protected target identity. Source descriptions/decorative roles do not establish PDF
behavior: measured LibreOffice 26.8.1.1 exports still fail PDF019 for office:title-only
links and PDF007/veraPDF for unlabelled decorative figures. Resolve publication failures
in the native source/exporter and retain strict validation; no automatic Name rewrite or
PDF tag repair is provided.

Text templates address named graphics and tables by their current context, for example
`content/frame[name=Logo]`, `content/note[1]/frame[name=Logo]` and
`content/note[1]/table[name=Data]`. Logical names/hrefs are percent-encoded where needed.
Existing authored graphic-name/image-reference/file-name selectors remain explicit group
selectors, and an unambiguous table name still selects that table. Qualified targets let
notes and main flow receive separate decisions. Unnamed table ordinals require a reviewed
fingerprint. A graphic without an authored name or image reference requires native identity
editing; templates do not invent an identity or a description. Header/footer notes in styles
are excluded from current-body target enumeration in both package and flat layouts.
