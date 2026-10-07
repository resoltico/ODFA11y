# Document workflow

Use the locked environment from the [README](../README.md#start-here). Keep the
original file: remediation refuses to write over its own source, and every command
writes to a path you choose.

## 1. Establish the baseline

```bash
uv run --no-sync odfa11y audit original.odt --schema --format json > before.json
uv run --no-sync odfa11y styles original.odt
```

An audit is read-only. Findings name a rule, a location and, where a configuration can
address them, a `remedy`: the key that holds the decision. `--schema` also validates
every member against the bundled official ODF schema for the declared version
(1.3 or 1.4); see [Accessibility and limits](ACCESSIBILITY.md#odf-schema-validation).
Audit accepts several files and detects ODT or PDF by content, so
`odfa11y audit a.odt b.pdf` reports both.

Open the original in Writer and identify its intended heading hierarchy, language,
data-table headers, meaningful graphic descriptions and intentional page breaks. These
decisions cannot be inferred from appearance.

## 2. Record the decisions

```bash
uv run --no-sync odfa11y template original.odt > document.toml
```

The template lists the open decisions with every line commented out. Uncomment and
complete only what you have decided; see [Configuration](CONFIGURATION.md). Then:

```bash
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml --dry-run
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml
```

Each target reports `applied`, `unchanged` or `failed`. Any failure (a table or graphic
that does not exist, a header count that conflicts, an invalid language) aborts the run
and writes nothing. Before publishing, the executor also checks that visible text is
unchanged (apart from counted spacer removals) and that the ODF schema shows no
violation the source did not already have. Publication is atomic.

## 3. Export and check the PDF

With LibreOffice installed (`soffice` or `libreoffice` on `PATH`, or `--soffice PATH`):

```bash
uv run --no-sync odfa11y export reviewed.odt reviewed.pdf
uv run --no-sync odfa11y audit reviewed.pdf --strict
uv run --no-sync odfa11y audit reviewed.pdf --verapdf --strict
```

The exporter uses a temporary LibreOffice profile, requests PDF/UA-1 and tagged PDF, and
publishes the PDF atomically. The built-in PDF audit is a fast smoke test of metadata,
tagging and structure (roles, headings, lists, tables, figures, links). `--verapdf` runs
the authoritative PDF/UA-1 validator and reports each failed rule with its clause and
test number. If veraPDF cannot be found the report contains the warning `VERA000`;
`--strict` makes that fail.

## 4. Compare the renders

```bash
uv run --no-sync odfa11y compare original.odt reviewed.odt --diff-dir diffs
```

Both documents are exported with the same LibreOffice and profile, then compared by page
count and size, text, links and rendered ink; see [Fidelity](FIDELITY.md). `compare`
also takes two PDFs directly.

## 5. Or do it all, with evidence

```bash
uv run --no-sync odfa11y pipeline original.odt --config document.toml \
  --output-dir evidence --verapdf --strict
uv run --no-sync odfa11y check-evidence evidence
```

The pipeline runs the stages in order and stops at the first failed gate; later stages
are recorded as skipped. The [evidence directory](EVIDENCE.md) is published whether the
run passed or failed.

## Exit statuses

| Status | Meaning |
| --- | --- |
| `0` | Success; warnings are allowed without `--strict`. |
| `1` | A report has warnings and `--strict` was supplied. |
| `2` | A report has errors (also argparse's status for invalid arguments), or `check-evidence` found problems. |
| `3` | An execution failure: invalid configuration, failed remediation, missing or failing external tool, unreadable input. The message is on stderr. |

For several reports the highest status wins. Informational findings never fail a command.

| Symptom | Action |
| --- | --- |
| Unknown TOML key or wrong type | Compare the field with [Configuration](CONFIGURATION.md); use unquoted booleans and positive integer header counts. |
| `remediate` lists failed targets | Fix the named table, graphic key or header count; a selector that matches nothing is an error. |
| "Remediation introduced ODF schema violations" | The operation produced markup the ODF schema rejects; the message lists the violations. |
| LibreOffice executable not found | Install LibreOffice and expose its CLI on `PATH`, or pass `--soffice`. |
| `FID005` after spacing or spacer changes | Content moved. Review the diff images; if the movement is intended set `fidelity.pagination = "may-change"`. |
