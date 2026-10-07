# Configuration

One TOML file holds every decision: document metadata, the choices that belong to a
document family, and the fidelity policy. It is never loaded automatically; pass
`--config document.toml` to `remediate`, `pipeline` or `compare`. There are no command-line
flags that duplicate these settings, so the file is the complete, reviewable statement of
what will change. Run `odfa11y template original.odt` to print a commented starter file for
the decisions an audit leaves open.

The file has two common tables, `[document]` and `[fidelity]`, and one table per document
family, named after the family (`[text]`, `[spreadsheet]`). A family table is read by that
family's adapter and applies only to documents of that family: configuring `[text]` for a
spreadsheet, or `[spreadsheet]` for a text document, is an error that stops the run before
anything is written, never a silently ignored section. Other families add their own tables
when they are supported (see [Architecture](ARCHITECTURE.md#document-families)).

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
# Data = { rows = 1, fingerprint = "0123456789ab" }

# Uncomment only after identifying the graphic and writing meaningful alt text.
# [text.alt_text.Logo]
# title = "Organisation name"
# description = "Description of the information conveyed by the graphic"
# fingerprint = "0123456789ab"

# [text.spacing]
# reference_text = "Text of the paragraph whose spacing is the reference"
# target_styles = ["BodyTight"]

# For spreadsheets (.ods, .fods) use the [spreadsheet] table instead of [text]. Sheet
# renames are refused for any sheet a formula, range or link refers to by name.
# [spreadsheet.sheet_names]
# "Sheet1" = "Budget 2026"
#
# [spreadsheet.alt_text."Company logo"]
# title = "Organisation name"
# description = "Description of the information conveyed by the picture"
# fingerprint = "0123456789ab"

[fidelity]
pagination = "same"
```

A test extracts this block and loads it through the real reader.

## Fields and defaults

| Table/key | Accepted value | When omitted |
| --- | --- | --- |
| `document.odf_version` | `"1.3"` or `"1.4"` (versions with a bundled schema). | The declared version is kept. |
| `document.title`, `document.description` | String; stripped before use. An empty string clears the field. | Existing value kept. |
| `document.language` | Language tag such as `"en-GB"`; sets metadata and, for families that keep a default language in their styles, that default too. | Existing languages kept. |
| `text.remediation.linkify_plain_addresses` | Boolean. | `false`. |
| `text.remediation.remove_empty_spacers` | Boolean; see [spacer removal](ACCESSIBILITY.md#spacer-removal). | `false`. |
| `text.table_headers.TABLE_NAME` | Positive integer (leading direct rows to mark as headers) or `{ rows = N, fingerprint = "…" }`. | No change. |
| `text.alt_text.KEY.title`, `.description` | String. | Existing text kept. |
| `text.alt_text.KEY.fingerprint` | The fingerprint of the addressed graphic(s). | Not checked. |
| `text.spacing.reference_text` | Text contained in the reference paragraph (required with `[text.spacing]`). | — |
| `text.spacing.target_styles` | Non-empty list of paragraph style names (required with `[text.spacing]`). | — |
| `text.spacing.exact_reference`, `text.spacing.include_headings` | Boolean. | `false`. |
| `spreadsheet.sheet_names."CURRENT"` | The new name of the sheet currently named `CURRENT`: not blank, without `[ ] * ? : / \`, no apostrophe at either end. | Sheet keeps its name. |
| `spreadsheet.alt_text.KEY.title`, `.description`, `.fingerprint` | As for `text.alt_text`, addressing frames in sheets. | See `text.alt_text`. |
| `fidelity.pagination` | `"same"` or `"may-change"`; see [Fidelity](FIDELITY.md). | `"same"`. |
| `fidelity.raster_tolerance` | Non-negative number. | `0.15`. |
| `fidelity.ink_threshold` | Integer 0–255. | `200`. |
| `fidelity.dpi` | Positive integer. | `72`. |

Unknown keys, wrong types, non-table sections and non-positive counts are rejected with
the offending key named. TOML booleans are `true`/`false`, not strings. An empty file is
valid and requests no change. Operations run in a fixed order (version, metadata, then the
family's operations: for text, linkify, spacer removal, graphics, header rows, spacing; for
spreadsheets, sheet names, then alt text), so a configuration always means the same thing.

## Every selector must match, and mean what you reviewed

A table name, graphic key or spacing reference that matches nothing fails the whole run
and nothing is written; the message lists every miss. Use a table's actual `table:name`
(not its position or caption). Graphic keys match the `draw:frame` name, the complete
image `href`, then the image file name, exactly; quote TOML keys containing dots or
slashes, for example `[text.alt_text."Pictures/logo.svg"]`. A table that already has header
rows is *unchanged* when the count agrees and a conflict when it does not.

Selectors are resolved before anything is edited. Two entries that address the same graphic
and set the *same field to different values* both fail; entries that set different fields,
or the same value, combine.

A **fingerprint** binds an entry to the object you reviewed. It is a short digest of the
object's identity and of facts no operation changes (a graphic's name, image file, size and
anchor; a table's name, shape and first-row text), so it stays the same after the plan has
been applied. If the document has drifted so that the key now addresses something else, the
entry fails with "no longer the object this plan was reviewed against". `odfa11y template`
prints the fingerprint of every object it suggests; leaving it out turns the check off.

Describing a graphic is a judgement about this document's meaning. The presence of a
title or description is only a structural check; do not give every image an arbitrary
description just to make a finding disappear.

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
  The test errs towards refusing (a sheet named `Data` is also blocked by a reference to
  `MyData.A1`). Update the references in Calc first, or rename in Calc.

The view settings (`settings.xml`) keep the old name; a test reloads a renamed document in
LibreOffice and exports it. Renaming also changes what Calc's default page header prints, see
[spreadsheet PDF exports](ACCESSIBILITY.md#spreadsheet-pdf-exports).

## Spacing

`[text.spacing]` copies the effective spacing of the paragraph containing `reference_text`
onto the paragraphs using each target style. It creates a derived style named
`A11ySpacing_<style>_<digest>` instead of rewriting shared styles, and recognises its own
result, so applying it again changes nothing. A style of that name is reused only when it is
provably ODFA11y's own earlier output (an unmodified derivation of the base style that
differs from it only in spacing); anything else of that name is left untouched and the
operation fails, so an author's style is never overwritten or reinterpreted. Use
`odfa11y styles` to choose the styles.

## Re-applying a configuration

Every operation reports `applied`, `unchanged` or `failed`. A second run over the result
reports everything `unchanged` and writes identical members. `remediate --dry-run` shows
the outcomes without writing.
