# Remediation configuration

Configuration records document-specific decisions for `remediate` and `pipeline`.
It is never loaded automatically: pass `--config document.toml` explicitly.
The ODT and PDF audits use their own CLI options.

## Example

Copy this single maintained example into `document.toml`. Replace the sample title,
language, table names and graphic descriptions with choices appropriate to the
actual document. Omit fields and tables you do not need.

```toml
[document]
target_version = "1.4"
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
```

Apply the configuration:

```bash
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml
```

A test extracts this TOML block and loads it through the actual configuration
reader. There is no separate root example file to keep in sync.

## Fields and defaults

| Table/key | Accepted value | When omitted |
| --- | --- | --- |
| `document.target_version` | String containing the target ODF declaration. | `"1.4"`. |
| `document.title` | String. | Existing title is retained. |
| `document.description` | String. | Existing description is retained. |
| `document.language` | Language-tag string, for example `"en-GB"`. | Existing metadata and default-style language are retained. |
| `remediation.linkify_plain_addresses` | TOML boolean. | `false`. |
| `remediation.remove_empty_spacers` | TOML boolean. | `false`; see [spacer removal](ACCESSIBILITY.md#spacer-removal). |
| `table_headers.TABLE_NAME` | Positive integer counting leading direct rows. | No header-row change for that table. |
| `alt_text.GRAPHIC_KEY.title` | String. | Existing graphic title is retained. |
| `alt_text.GRAPHIC_KEY.description` | String. | Existing graphic description is retained. |

Unknown keys, incorrect types, non-table sections and nonpositive header counts
are rejected. TOML booleans must be `true` or `false`, not quoted strings. An empty
configuration is valid and still requests the default ODF version declarations.
Empty title and description strings are accepted and can clear those fields;
these values are stripped before application. Invalid language values can fail
when remediation applies them. Use omission when you mean to retain a value.

Setting an ODF declaration does not convert every construct to the target format.
Re-audit and, where needed, validate against official schemas. Language handling
sets metadata plus the default paragraph style; it does not assign languages to
every multilingual text run or provide complete language-tag validation.

## Table headers

Use the table's actual `table:name`, not its position or visible caption. The
requested count must not exceed its direct rows. Tables with an existing
`table:table-header-rows` wrapper are left unchanged; unmatched names are skipped.
ODFA11y does not infer the intended header relationships.

Quote names containing spaces or punctuation in TOML. On the CLI, a named choice
such as `--table-header 'Sales figures=1'` overrides the configured count for that
table. Repeat the option for other tables.

## Graphic alternative text

Graphic keys are matched in this order: `draw:frame` name, complete image `href`,
then image basename. Matching is exact. Quote TOML keys containing dots or slashes,
for example `[alt_text."Pictures/logo.svg"]`. Unmatched keys are skipped.

The presence of a title or description is only a structural check. Describe what
the graphic means in this document; avoid treating every image as a logo or giving
it an arbitrary description just to make a finding disappear.

## CLI overrides

Explicit `--title`, `--description`, `--language` and `--target-version` options
override the corresponding configured values. `--linkify` and `--no-linkify`
explicitly enable or disable linkification.

`--alt-map alt-text.json` accepts a JSON object mapping graphic keys to either a
description string or an object containing `title` and/or `description`:

```json
{
  "Logo": {
    "title": "Organisation name",
    "description": "Description of the graphic's meaning"
  }
}
```

JSON entries override configured entries with the same key as a whole; fields are
not merged within an entry. Unspecified fields are not applied to the graphic.
Names not present in the document are skipped, so review the reported changes.
