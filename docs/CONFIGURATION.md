# Configuration

One TOML file records explicit remediation decisions and the fidelity policy. Pass
`--config document.toml` to `remediate`, `pipeline` or `compare`; configuration is never
loaded automatically. `compare` reads only the fidelity policy and does not apply edits.
Run `odfa11y template original.odt` for a commented starter file bound to the document.

Common tables are `[document]` and `[fidelity]`. Family tables are `[text]`,
`[spreadsheet]`, `[presentation]`, `[drawing]`, `[formula]`, `[image]` and `[database]`;
Chart uses common document metadata. The drawing adapter serves the standard's graphics
family. Operations for a different family fail before publication; they are never silently
ignored. See [family capabilities](ACCESSIBILITY.md#document-families).

## Example

Replace the sample values with reviewed decisions and delete unused entries.

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
# Use the exact current target and fingerprint printed by odfa11y template.
# "content/table[name=Data]" = { rows = 1, fingerprint = "0123456789abcdef" }

# [text.graphics."content/frame[name=Logo]"]
# title = "Organisation name"
# description = "Description of the information conveyed by the graphic"
# fingerprint = "0123456789abcdef"

# [text.spacing]
# reference_text = "Text of the paragraph whose spacing is the reference"
# target_styles = ["BodyTight"]

# For spreadsheets, use [spreadsheet] instead of [text].
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

The example block is loaded by the configuration test suite.

## Fields and defaults

| Table/key | Accepted value | When omitted |
| --- | --- | --- |
| `document.odf_version` | `"1.3"` or `"1.4"`, the versions with bundled ODF schemas. | Declared version kept. |
| `document.title`, `document.description` | Nonblank string; stripped before use. | Existing metadata kept. |
| `document.language` | Well-formed BCP 47 tag; scripts, numeric regions, variants, extensions, private use and grandfathered syntax are accepted. Separators/casing normalize without registry lookup or alias rewriting. | Existing languages kept. |
| `text.remediation.linkify_plain_addresses` | Boolean. | `false`. |
| `text.remediation.remove_empty_spacers` | Boolean; see [spacer removal](ACCESSIBILITY.md#spacer-removal). | `false`. |
| `text.table_headers."TARGET"` | `{ rows = N, columns = M, fingerprint = "…" }`; at least one positive leading logical count. Repeats count; an omitted axis stays unchanged. | No change. |
| `text.heading_levels."TARGET"` | `{ level = N, fingerprint = "…" }`, level 1–10. Exact report target; ordinal targets require the fingerprint. | No change. |
| `<family>.graphics.KEY.title`, `.description` | Nonblank string for Text, Spreadsheet, Presentation, Drawing or Image. | Existing alternative kept. |
| `<family>.graphics.KEY.fingerprint` | Reviewed identity of the addressed graphic(s); mandatory for explicit roles. | Optional for alternatives without a role decision. |
| `<family>.graphics.KEY.decorative` | Boolean; requires ODF 1.4 and reviewed fingerprint. | Existing role kept. |
| `<family>.links."TARGET"` | `{ description = "…", fingerprint = "…" }` for Text, Spreadsheet, Presentation or Drawing; both strings nonblank. | Existing `office:title` kept. |
| `text.spacing.reference_text` | Non-empty text contained in the reference paragraph; required with spacing. | — |
| `text.spacing.target_styles` | Non-empty list of paragraph style names; required with spacing. | — |
| `text.spacing.exact_reference`, `text.spacing.include_headings` | Boolean. | `false`. |
| `spreadsheet.sheet_names."CURRENT"` | Nonblank replacement; no `[ ] * ? : / \` or apostrophe at either end. | Sheet name kept. |
| `presentation.pages."PAGE"`, `drawing.pages."PAGE"` | Optional strings `title`, `description`, `fingerprint`, and complete `navigation = ["shape-id", …]`. | Existing metadata/order kept. |
| `formula.alternative`, `formula.fingerprint` | Nonblank spoken alternative and optional reviewed expression digest. | Native MathML `alttext` kept. |
| `database.descriptions."TARGET"` | `{ text = "…", fingerprint = "…" }`; exact report target; ordinal targets require the fingerprint. | Existing description kept. |
| `fidelity.pagination` | `"same"` or `"may-change"`; see [Fidelity](FIDELITY.md). | `"same"`. |
| `fidelity.raster_tolerance` | Finite non-negative number; no upper cap. | `0.15`. |
| `fidelity.ink_threshold` | Integer 0–255. | `200`. |
| `fidelity.dpi` | Positive integer. | `72`. |

Unknown keys, wrong types, non-table sections and non-positive counts are rejected with
the offending key named. TOML booleans are `true`/`false`, not strings. An empty file
requests no change. Operations run in canonical order: version, metadata, then family
operations. Text orders linkification, spacer removal, graphics, headings, headers,
spacing and link descriptions; spreadsheets order sheet names, graphics and links.

Language decisions set metadata and all three default script channels where supported,
retaining named, automatic and direct content overrides. Source tag preservation and
native exporter behavior are separate; see [language limits](ACCESSIBILITY.md#language).

## Every selector must match, and mean what you reviewed

A selector that matches nothing fails the run; no candidate is published. Multi-target
operations resolve and validate their targets before that operation edits them. Publication
is atomic across the complete plan; this does not make direct low-level operation calls a
whole-plan transaction.

Use exact logical targets from the report/template wherever supplied. Text templates
qualify current body, note and text-box contexts, for example `content/frame[name=Logo]`,
`content/note[1]/frame[name=Logo]` and `content/note[1]/table[name=Data]`. Names and identities
percent-encode reserved delimiters. Header/footer notes in styles are outside current-body
target enumeration in both package and flat layouts.

Graphic keys also accept authored drawing names, complete image hrefs and image filenames;
these explicit selectors can address a group of matching objects. Quote TOML keys containing
dots or slashes. A graphic without an authored name or image reference needs identity editing
in the native application; templates do not invent one.

Table keys accept an exact logical target or an unambiguous `table:name`, not a caption.
An unnamed table's ordinal target requires its reviewed fingerprint. Header counts already
matching the selected axis report `unchanged`; a different explicit count revises the
boundary. Spans crossing the boundary and non-leading header bands refuse.

Two entries addressing one graphic fail if they assign different values to the same
field; equal values and distinct fields combine.

A **fingerprint** binds a decision to reviewed protected facts: structural position,
content, geometry, references, relevant styles and payloads, excluding the accessibility
metadata the operation may edit. Drift fails the decision. Fingerprints are mandatory for
ordinal heading/table/database targets, all link descriptions and explicit graphic roles;
other decisions can opt into the check. Graphic/link/page fingerprints include descendant
graphical style dependencies. Missing or unsupported descendant styles refuse metadata
edits rather than treating an unresolved identity as reviewed.

## Heading levels

Use `content/heading[2]` or `content/heading[id=section]` exactly as reported. The explicit
level changes only `text:outline-level`; the fingerprint excludes that field so reapplication
is unchanged. Changed content, duplicate identities and stale ordinal selections refuse.

## Renaming sheets

`[spreadsheet.sheet_names]` maps current names to replacements. Every entry is checked
before the first rename. Unknown or duplicate current names, invalid names, case-insensitive
collisions, chains and swaps refuse. A case-only change is allowed. If the old name is gone
and its unique replacement exists, reapplication reports `unchanged`.

A sheet that anything may refer to by name cannot be renamed: references are not rewritten.
Matching includes case variants and URL escapes, dotted plain/quoted references and links to
a bare sheet name. It is conservative: `Data` can match `MyData.A1`. Embedded charts/objects,
embedded scripts and dynamic `INDIRECT`, `ADDRESS` or `HYPERLINK` formulas block every rename.
Update references or rename in Calc instead.

Renaming updates table-view/script-configuration keys and active-sheet selection in
`settings.xml` or flat XML. Calc's default printed header includes the sheet name, so a
rename can fail text fidelity; see [spreadsheet exports](ACCESSIBILITY.md#spreadsheet-pdf-exports).

## Presentation and drawing pages

Page keys are exact unique `draw:name` values. Supplied title/description metadata does
not create visible heading text or guarantee a PDF heading role. Navigation must include
every top-level shape exactly once, with a group as one entry, using existing identities
unique throughout the content document. Missing, duplicate or partial identities refuse;
set explicit identities/navigation in the native application first.

Family graphic tables describe frames and eligible vector shapes. Native empty notes
placeholders and generated page thumbnails do not require invented alternatives. Notes,
annotations, hidden pages/layers, groups and reading order remain human review matters.

## Graphic roles and link descriptions

The Python decision `GraphicAlternative` and family `SetGraphicAlternatives` operations
accept title, description, decorative role and fingerprint; omission preserves the field.
`decorative = true` is an explicit decision and cannot combine with supplied title or
description, including overlapping selectors. Existing authored alternatives remain and
produce `GRAPHIC002` for review. `false` restores meaningful status and ordinary alternative
requirements. Either explicit role needs ODF 1.4 and its reviewed fingerprint; an explicit
`document.odf_version = "1.4"` may relabel a source subject to the schema regression gate.

Roles use standard `draw:decorative` on `style:graphic-properties`. Target-specific derived
styles preserve visual properties, legal parents and ordered class overlays. Reapplication
reuses only a proven isolated derivation. A role change needs an established explicit style
or class reference: inserting a style on an implicitly styled object can change native
placement and wrapping. A matching explicit false decision can remain unchanged.

Missing/ambiguous styles, cycles, invalid roles and mixed graphic/presentation precedence
refuse. Optional absent styles resolve to the standard meaningful default. Text-bearing,
control/action, hyperlink and explicit group role edits refuse decorative intent. Existing
group roles never suppress child alternatives or payload checks.

`LinkDescription` and family `SetLinkDescriptions` write only native `office:title` on
eligible `text:a`/`draw:a`. Each exact target needs a nonblank description and reviewed
fingerprint. Legal Draw link IDs appear as `content/link[id=…]`; other links use ordinals,
with note/text-box prefixes where applicable. Writer links have no native XML ID slot.
Repeated or ambiguous targets refuse. Hrefs, visible labels, geometry, target Names and
incoming references remain protected; no description is inferred from a URL.

```text
# [text.links."content/link[1]"]
# description = "Annual report downloads"
# fingerprint = "COPY_FROM_THE_CURRENT_TEMPLATE"
```

Ordinal link descriptions cannot combine with address linkification or table-header edits
that may change enumeration. Apply the structural plan, regenerate the template, review the
link decisions and apply them separately. Page/graphic/link metadata decisions compose and
reapply. Source roles/descriptions do not guarantee exporter behavior; see
[graphic roles](ACCESSIBILITY.md#graphic-roles) and [links](ACCESSIBILITY.md#link-descriptions).

## Spacing

`[text.spacing]` copies effective spacing from the selected reference paragraph to
paragraphs using target styles. `exact_reference` requires full text equality rather than
a contained string; `include_headings` permits selected headings. `odfa11y styles` shows
usage and effective spacing.

The operation creates `A11ySpacing_<style>_<digest>` instead of rewriting shared styles.
It reuses a name only for a proven unmodified derivation differing from its base solely in
spacing; authored or unproven collisions refuse. Paragraph `text:class-names` and
`text:cond-style-name` precedence is unestablished: inspection reports `TXT062`, and affected
reference/target paragraphs refuse. Shared derivations consumed by excluded, unselected or
unestablished content also refuse changes that would affect those consumers.

## Re-applying a configuration

Operations report `applied`, `unchanged` or `failed`. Reapplication to the result reports
unchanged outcomes without accumulating edits. `remediate --dry-run` shows proposed outcomes
and writes nothing. Preservation/schema failures prevent publication even for a dry run.

## Formula, Chart, Image and Base

Formula decisions set native MathML `alttext` and language, preserving the expression and
StarMath annotation. Native expressions use the bundled normative MathML 3 grammar; flat
`office:formula` wrappers are not accepted. Math's exporter lacks required tagging; source
success does not establish PDF/UA conformance.

Chart uses `document.description` for its nonvisual alternative and `document.title` for
identification, without rewriting visible chart titles. Data, series, ranges, formulas and
labels remain protected. External providers are reported, never fetched.

Image uses `[image.graphics]`. Malformed payloads fail; active/external SVG declarations
need review. Standard image media types are deprecated by ODF.

Base uses targets such as `[database.descriptions."content/query[name=Example]"]`, with
nonblank `text` and optional fingerprint except for ordinal targets. Declared objects use
`db:description` or form-control `form:title`. SQL, bindings, settings and opaque database,
form and report bytes remain protected. Connections, queries and macros are never executed.
Chart, Image and Base have no native PDF filter; production fails the required PDF boundary.

When a native package omits optional `meta.xml`, explicit metadata creates the standard
part and manifest entry using the declared supported ODF version.
