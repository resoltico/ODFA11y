# Document workflow

Restore the [locked environment](../README.md#start-here) and keep the original source.
Commands recognize packaged/flat ODF by declared media type and PDF by content.

## Audit

```sh
uv run --no-sync odfa11y audit original.odt --schema --format json > before.json
uv run --no-sync odfa11y plan original.odt > reviewed.toml
```

Audit is read-only. Reports contain registered rules, [logical locations](RULES.md#locations),
typed facts and open questions. Paragraph style diagnostics are part of text audits.
Multiple inputs retain completed reports through later input/tool failures. CLI JSON is a
single `inputs` envelope for one or several inputs, matching the [audit result](API.md).
[SARIF](SARIF.md) requires source preflight and refuses partial output on execution failure.

## Review and apply

Edit the [plan](PLAN.md): headers and fingerprints are already live. Uncomment and
fill only the answer fields you have reviewed. Unanswered blocks remain inert. Source
binding and fingerprints are mandatory; appearance does not establish intended semantics.

```sh
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan reviewed.toml --dry-run
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan reviewed.toml
```

Outcomes are `applied`, `unchanged` or `failed`. A candidate with any operation,
preservation or applicable schema failure is unpublished. Later independent outcomes
remain recorded. A passing preview exits 0 with `publication="preview"`; a refusal exits 2.
Use a separate reviewed plan for structural edits and ordinal language/link descriptions;
see [preservation boundaries](ACCESSIBILITY.md#preservation-boundaries).

## Check the publication

```sh
uv run --no-sync odfa11y doctor
uv run --no-sync odfa11y export reviewed.odt reviewed.pdf
uv run --no-sync odfa11y audit reviewed.pdf --validate --strict
uv run --no-sync odfa11y compare original.odt reviewed.odt --diff-dir differences
```

Export requests tagging/PDF/UA-1. Check the actual PDF, the independent validator and
[fidelity](FIDELITY.md). [Measured capabilities](CAPABILITIES.md) describe selected
exporter behavior; they never waive a document-level failure.

## Retain evidence

```sh
uv run --no-sync odfa11y run original.odt --plan reviewed.toml \
  --output-dir evidence --profile production
uv run --no-sync odfa11y verify-evidence evidence
```

| Profile | Required assurance |
| --- | --- |
| `source` | Source inspection, remediation and candidate audit; warnings allowed. |
| `pdf` (default) | Source work plus native/PDF/fidelity checks; warnings allowed. |
| `production` | All stages, required veraPDF, errors and warnings fail. |

Source findings inform remediation; the candidate audit gates acceptance. Stages run whenever
their declared inputs exist: candidate findings do not prevent export, and validator failures do
not prevent fidelity. A refused candidate is never exported. Unsupported stages are
`not-applicable`; production requires PDF assurance. Required tools and plans are checked
before a run publishes output; batch preparation failures appear only in `batch.json`. [Evidence](EVIDENCE.md) retains completed artifacts and failures when the
output location can be safely published. Integrity verification checks recorded bytes.
Read `REVIEW.md` and perform the [human checks](ACCESSIBILITY.md#human-acceptance).

## Resolve a refusal

Create and review a newly bound plan with `odfa11y plan NEW_SOURCE --from OLD_PLAN`.
Only answers whose target identities still match remain active. For `NATIVE001`/`NATIVE002`/`NATIVE003`, inspect the
[native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies).
For schema failures, inspect the introduced violations. For fidelity failures, review
actual differences before changing policy. Use a fresh evidence directory after interruption.

[Generated command reference](CLI.md#exit-statuses) owns exit values and precedence.
Progress is append-only on interactive text stderr; redirected stderr and JSON/SARIF
remain quiet. A disconnected progress stream does not stop document work.
