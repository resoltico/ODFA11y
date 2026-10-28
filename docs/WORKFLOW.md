# Document workflow

Restore the [locked environment](../README.md#start-here) and keep the original source.
Commands recognize packaged/flat ODF by declared media type and PDF by content.

## Inspect

```sh
uv run --no-sync odfa11y audit original.odt --schema --format json > before.json
uv run --no-sync odfa11y plan original.odt > reviewed.toml
```

Audit is read-only. Reports contain registered rules, [logical locations](RULES.md#locations),
typed facts and open questions. Paragraph style diagnostics are part of text audits.
Multiple inputs retain completed reports through later input/tool failures. CLI JSON is a
report object or array; the root API also exposes a per-input [audit result](API.md).
[SARIF](SARIF.md) requires source preflight and refuses partial output on execution failure.

## Review and apply

Edit the [plan](PLAN.md): uncomment the selected tables, their fingerprints and the
answers you have supplied. Leave unused placeholders commented. Source binding and
fingerprints remain mandatory; appearance does not establish intended semantics.

```sh
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan reviewed.toml --dry-run
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan reviewed.toml
```

Outcomes are `applied`, `unchanged` or `failed`. A candidate with any operation,
preservation or applicable schema failure is unpublished. Later independent outcomes
remain recorded. A passing preview exits 0 with `published=false`; a refusal exits 2.
Use a separate reviewed plan for structural edits and ordinal language/link descriptions;
see [preservation boundaries](ACCESSIBILITY.md#preservation-boundaries).

## Check the publication

```sh
uv run --no-sync odfa11y doctor
uv run --no-sync odfa11y export reviewed.odt reviewed.pdf
uv run --no-sync odfa11y audit reviewed.pdf --verapdf --strict
uv run --no-sync odfa11y compare original.odt reviewed.odt --diff-dir differences
```

Export requests tagging/PDF/UA-1. Check the actual PDF, the independent validator and
[fidelity](FIDELITY.md). [Measured capabilities](CAPABILITIES.md) describe selected
exporter behavior; they never waive a document-level failure.

## Retain evidence

```sh
uv run --no-sync odfa11y pipeline original.odt --plan reviewed.toml \
  --output-dir evidence --profile production
uv run --no-sync odfa11y verify evidence
```

| Profile | Required assurance |
| --- | --- |
| `source` | Source inspection, remediation and candidate audit; warnings allowed. |
| `verify` (default) | Source work plus native/PDF/fidelity checks; warnings allowed. |
| `production` | All stages, required veraPDF, errors and warnings fail. |

Source findings inform remediation; the candidate audit gates it. Later stages stop at a
failed gate. Unsupported stages are `not-applicable`; production fails required missing
PDF assurance. [Evidence](EVIDENCE.md) retains completed artifacts and failures when the
output location can be safely published. Integrity verification checks recorded bytes.
Read `REVIEW.md` and perform the [human checks](ACCESSIBILITY.md#human-acceptance).

## Resolve a refusal

Regenerate/review a stale plan; use `--rebind` only to explicitly accept a different source
hash. It does not waive fingerprints or guards. For `NATIVE001`/`NATIVE002`, inspect the
[native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies).
For schema failures, inspect the introduced violations. For fidelity failures, review
actual differences before changing policy. Use a fresh evidence directory after interruption.

[Generated command reference](CLI.md#exit-statuses) owns exit values and precedence.
Progress is append-only on interactive text stderr; redirected stderr and JSON/SARIF
remain quiet. A disconnected progress stream does not stop document work.
