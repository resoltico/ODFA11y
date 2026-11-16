# Decision plans

`odfa11y plan SOURCE` prints finding-driven human questions. Headers and target fingerprints
are live; answer fields are commented. A block without answers is inert and appears as
unanswered in previews. Supply only reviewed answers; blank alternative text is invalid.
`--all` adds clearly marked optional overrides with no raised finding.

Plans bind to source bytes. Use `plan NEW_SOURCE --from OLD_PLAN` after changes: matching
kind/path/fingerprint answers carry live; nonmatching answers remain comments with reasons.
Unsupported plan formats refuse with a regeneration remedy. Answered stale fingerprints are errors;
stale unanswered blocks warn without editing anything. Independent load problems are
reported together. Content answers remain bound to the reviewed target identity.

`remediate --dry-run` returns an in-memory candidate preview, resolved/remaining findings,
unanswered blocks, all outcomes and schema assurance. A requested edit can succeed while
related findings remain; inspect the prediction. See the [worked example](WALKTHROUGH.md).
`run --plan` consumes the same plan; `compare --plan` uses its fidelity policy.

`pagination = "same"` accepts tolerance/threshold parameters at fixed 72 dpi;
`pagination = "may-change"` refuses them. See [fidelity](FIDELITY.md). Language edits retain
unrelated channels/overrides, and never infer a language. Source guards and human review
remain required.

## Example


The SHA-256 value must identify the exact reviewed source bytes. Generate it with
the `plan` command; the value below is illustrative.

```toml
[plan]
schema_version = 1
generator = "0.9.0"
source.sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[decisions."document.metadata"]
title = "Example report"
description = "Summary of the reporting period"
language = "en-GB"

[fidelity]
pagination = "same"
```

<!-- generated decisions -->
## Registered decisions

### `database.description`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `text` | yes | string; xml text; nonblank | Explain the declared object without changing SQL or bindings. |

### `document.metadata`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `title` | no | string; xml text; nonblank | Document title identifying its purpose. |
| `description` | no | string; xml text; nonblank | Document description and context. |
| `language` | no | string; language tag | Intended default language, preserving explicit local overrides. |

Supply at least one of: `title`, `description`, `language`.

### `document.odf_version`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `version` | yes | One of `1.3`, `1.4` | ODF version whose result must satisfy schema guards. |

### `formula.alternative`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `alternative` | yes | string; xml text; nonblank | Write the formula's spoken meaning in its intended language. |

### `graphic.alternative`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `title` | no | string; xml text; nonblank | Accessible title. |
| `description` | no | string; xml text; nonblank | Explain the graphic's meaning. |
| `decorative` | no | boolean | Explicit decorative role, subject to source safety guards. |

Supply at least one of: `title`, `description`, `decorative`.

### `heading.level`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `level` | yes | integer; at least 1; at most 10 | Intended outline level. |

### `language.target`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `western` | no | string; language tag | Language for the target western-script channel. |
| `asian` | no | string; language tag | Language for the target Asian-script channel. |
| `complex` | no | string; language tag | Language for the target complex-script channel. |

Supply at least one of: `western`, `asian`, `complex`.

### `link.description`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `description` | yes | string; xml text; nonblank | Explain the link's purpose in its reading context. |

### `page.metadata`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `title` | no | string; xml text; nonblank | Accessible page title. |
| `description` | no | string; xml text; nonblank | Page purpose and context. |

Supply at least one of: `title`, `description`.

### `page.navigation`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `navigation` | yes | List of string; xml text; nonblank; at least 0 items. | Complete reading order of the page's existing shape identities. |

### `sheet.name`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `name` | yes | string; sheet name | Name identifying what the sheet contains. |

### `table.headers`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `rows` | no | integer; at least 1 | Number of leading logical header rows. |
| `columns` | no | integer; at least 1 | Number of leading logical header columns. |

Supply at least one of: `rows`, `columns`.

### `text.linkify_addresses`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `enabled` | yes | boolean | Enable only after reviewing all affected content. |

### `text.remove_spacers`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `enabled` | yes | boolean | Enable only after reviewing all affected content. |

### `text.spacing`

Scope: document.

| Field | Required | Value constraints | Help |
| --- | --- | --- | --- |
| `reference_text` | yes | string; nonblank | Authored text identifying the reference paragraph. |
| `target_styles` | yes | List of string; nonblank; at least 1 items. | Existing paragraph styles selected for spacing normalization. |
| `exact_reference` | no | boolean | Match the entire reference paragraph. |
| `include_headings` | no | boolean | Also apply to headings using the selected styles. |
