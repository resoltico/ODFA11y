# Configuration

One TOML file holds every decision: document metadata, remediation choices, graphic
descriptions, table headers, spacing and the fidelity policy. It is never loaded
automatically; pass `--config document.toml` to `remediate`, `pipeline` or `compare`.
There are no command-line flags that duplicate these settings, so the file is the
complete, reviewable statement of what will change. Run `odfa11y template original.odt`
to print a commented starter file for the decisions an audit leaves open.

## Example

Copy this single maintained example, replace the sample values with choices appropriate
to the actual document and delete what you do not need.

```toml
[document]
# odf_version = "1.4"   # relabel the package; omit to keep the declared version
title = "Example report"
description = "Summary of the reporting period"
language = "en-GB"

[remediation]
linkify_plain_addresses = true
# Opt in only after reviewing layout and intentional page-break semantics.
remove_empty_spacers = false

[table_headers]
# Uncomment only for a real data table named Data with one header row.
# Data = 1

# Uncomment only after identifying the graphic and writing meaningful alt text.
# [alt_text.Logo]
# title = "Organisation name"
# description = "Description of the information conveyed by the graphic"

# [spacing]
# reference_text = "Text of the paragraph whose spacing is the reference"
# target_styles = ["BodyTight"]

[fidelity]
pagination = "same"
```

A test extracts this block and loads it through the real reader.

## Fields and defaults

| Table/key | Accepted value | When omitted |
| --- | --- | --- |
| `document.odf_version` | `"1.3"` or `"1.4"` (versions with a bundled schema). | The declared version is kept. |
| `document.title`, `document.description` | String; stripped before use. An empty string clears the field. | Existing value kept. |
| `document.language` | Language tag such as `"en-GB"`; sets metadata and the default paragraph style. | Existing languages kept. |
| `remediation.linkify_plain_addresses` | Boolean. | `false`. |
| `remediation.remove_empty_spacers` | Boolean; see [spacer removal](ACCESSIBILITY.md#spacer-removal). | `false`. |
| `table_headers.TABLE_NAME` | Positive integer: leading direct rows to mark as headers. | No change. |
| `alt_text.KEY.title`, `.description` | String. | Existing text kept. |
| `spacing.reference_text` | Text contained in the reference paragraph (required with `[spacing]`). | — |
| `spacing.target_styles` | Non-empty list of paragraph style names (required with `[spacing]`). | — |
| `spacing.exact_reference`, `spacing.include_headings` | Boolean. | `false`. |
| `fidelity.pagination` | `"same"` or `"may-change"`; see [Fidelity](FIDELITY.md). | `"same"`. |
| `fidelity.raster_tolerance` | Non-negative number. | `0.15`. |
| `fidelity.ink_threshold` | Integer 0–255. | `200`. |
| `fidelity.dpi` | Positive integer. | `72`. |

Unknown keys, wrong types, non-table sections and non-positive counts are rejected with
the offending key named. TOML booleans are `true`/`false`, not strings. An empty file is
valid and requests no change. Operations run in a fixed order (version, metadata,
linkify, spacer removal, graphics, header rows, spacing), so a configuration always means
the same thing.

## Every selector must match

A table name, graphic key or spacing reference that matches nothing fails the whole run
and nothing is written; the message lists every miss. Use a table's actual `table:name`
(not its position or caption). Graphic keys match the `draw:frame` name, the complete
image `href`, then the image file name, exactly; quote TOML keys containing dots or
slashes, for example `[alt_text."Pictures/logo.svg"]`. A table that already has header
rows is *unchanged* when the count agrees and a conflict when it does not.

Describing a graphic is a judgement about this document's meaning. The presence of a
title or description is only a structural check; do not give every image an arbitrary
description just to make a finding disappear.

## Spacing

`[spacing]` copies the effective spacing of the paragraph containing `reference_text`
onto the paragraphs using each target style. It creates a derived style named
`A11ySpacing_<style>` instead of rewriting shared styles, and recognises its own result,
so applying it again changes nothing. Use `odfa11y styles` to choose the styles.

## Re-applying a configuration

Every operation reports `applied`, `unchanged` or `failed`. A second run over the result
reports everything `unchanged` and writes identical members. `remediate --dry-run` shows
the outcomes without writing.
