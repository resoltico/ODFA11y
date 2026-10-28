# Decision plans

Run `odfa11y plan original.odt` to print a source-bound TOML plan. Review each
question, supply its answer and enable only the reviewed decision tables. Pass
`--plan reviewed.plan.toml` to `remediate` or `pipeline`. `compare` reads its fidelity
policy. Plans are never loaded automatically.

Target-language decisions preserve other script channels and authored inline overrides.
Apply structural edits first and regenerate/review ordinal targets afterward; the combined
plan refuses. Tables with ambiguous intent/relationships require native editing. See
[preservation boundaries](ACCESSIBILITY.md#preservation-boundaries).

## Example

The SHA-256 value must identify the exact reviewed source bytes. Generate it with
the `plan` command; the value below is illustrative.

```toml
[plan]
format = 1
generator = "0.8.0"
source.sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[decisions."document.metadata"]
title = "Example report"
description = "Summary of the reporting period"
language = "en-GB"

[fidelity]
pagination = "same"
```

Each registered decision kind defines its fields. Document decisions bind through
the header. Targeted decisions additionally require the canonical target path and
16-character fingerprint printed by the audit or plan command. Do not invent
fingerprints or infer answers from filenames. Unknown fields, old configuration
tables, invalid types and missing binding metadata are rejected.

`--rebind` explicitly permits a different source digest. It does not bypass target
fingerprints or preservation checks. Reapplying a reviewed answer to a remediated
source therefore requires rebind and still checks the target's preserved identity.

Remediation reports every operation outcome and structured refusal. A refused
candidate is not published and exits 2. A successful `--dry-run` exits 0 with
`published=false`; a failing preview exits 2 and retains the refusal evidence.

<!-- generated decisions -->
## Registered decisions

### `database.description`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `text` | yes | `{"type":"string","format":"odfa11y-xml-text","pattern":"\\S"}` | Explain the declared object without changing SQL or bindings. |

### `document.metadata`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `title` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-xml-text","pattern":"\\S"}` | Document title identifying its purpose. |
| `description` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-xml-text","pattern":"\\S"}` | Document description and context. |
| `language` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"pattern":"\\S","format":"odfa11y-language-tag"}` | Intended default language, preserving explicit local overrides. |

Required-field alternatives: `[{"required": ["title"], "properties": {"title": {"not": {"type": "null"}}}}, {"required": ["description"], "properties": {"description": {"not": {"type": "null"}}}}, {"required": ["language"], "properties": {"language": {"not": {"type": "null"}}}}]`.

### `document.odf_version`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `version` | yes | `{"type":"string","enum":["1.3","1.4"]}` | ODF version whose result must satisfy schema guards. |

### `formula.alternative`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `alternative` | yes | `{"type":"string","format":"odfa11y-xml-text","pattern":"\\S"}` | Write the formula's spoken meaning in its intended language. |

### `graphic.alternative`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `title` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-xml-text"}` | Accessible title; empty text explicitly clears it. |
| `description` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-xml-text"}` | Explain the graphic's meaning; empty text clears it. |
| `decorative` | no | `{"anyOf":[{"type":"boolean"},{"type":"null"}]}` | Explicit decorative role, subject to source safety guards. |

Required-field alternatives: `[{"required": ["title"], "properties": {"title": {"not": {"type": "null"}}}}, {"required": ["description"], "properties": {"description": {"not": {"type": "null"}}}}, {"required": ["decorative"], "properties": {"decorative": {"not": {"type": "null"}}}}]`.

### `heading.level`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `level` | yes | `{"type":"integer","minimum":1,"maximum":10}` | Intended outline level. |

### `language.target`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `western` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-language-tag"}` | Language for the target western-script channel. |
| `asian` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-language-tag"}` | Language for the target Asian-script channel. |
| `complex` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-language-tag"}` | Language for the target complex-script channel. |

Required-field alternatives: `[{"required": ["western"], "properties": {"western": {"not": {"type": "null"}}}}, {"required": ["asian"], "properties": {"asian": {"not": {"type": "null"}}}}, {"required": ["complex"], "properties": {"complex": {"not": {"type": "null"}}}}]`.

### `link.description`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `description` | yes | `{"type":"string","format":"odfa11y-xml-text","pattern":"\\S"}` | Explain the link's purpose in its reading context. |

### `page.metadata`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `title` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-xml-text"}` | Accessible page title. |
| `description` | no | `{"anyOf":[{"type":"string"},{"type":"null"}],"format":"odfa11y-xml-text"}` | Page purpose and context. |

Required-field alternatives: `[{"required": ["title"], "properties": {"title": {"not": {"type": "null"}}}}, {"required": ["description"], "properties": {"description": {"not": {"type": "null"}}}}]`.

### `page.navigation`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `navigation` | yes | `{"type":"array","items":{"type":"string","pattern":"\\S","format":"odfa11y-xml-text"}}` | Complete reading order of the page's existing shape identities. |

### `sheet.name`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `name` | yes | `{"type":"string","format":"odfa11y-sheet-name"}` | Name identifying what the sheet contains. |

### `table.headers`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `rows` | no | `{"anyOf":[{"type":"integer"},{"type":"null"}],"minimum":1}` | Number of leading logical header rows. |
| `columns` | no | `{"anyOf":[{"type":"integer"},{"type":"null"}],"minimum":1}` | Number of leading logical header columns. |

Required-field alternatives: `[{"required": ["rows"], "properties": {"rows": {"not": {"type": "null"}}}}, {"required": ["columns"], "properties": {"columns": {"not": {"type": "null"}}}}]`.

### `text.linkify_addresses`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `enabled` | yes | `{"type":"boolean"}` | Enable only after reviewing all affected content. |

### `text.remove_spacers`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `enabled` | yes | `{"type":"boolean"}` | Enable only after reviewing all affected content. |

### `text.spacing`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `reference_text` | yes | `{"type":"string","pattern":"\\S"}` | Authored text identifying the reference paragraph. |
| `target_styles` | yes | `{"type":"array","items":{"type":"string","pattern":"\\S"},"minItems":1}` | Existing paragraph styles selected for spacing normalization. |
| `exact_reference` | no | `{"type":"boolean"}` | Match the entire reference paragraph. |
| `include_headings` | no | `{"type":"boolean"}` | Also apply to headings using the selected styles. |
