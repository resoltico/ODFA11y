# Document workflow

Use the locked environment from the [README](../README.md#start-here). Keep the
original file: remediation refuses to write over its own source, and every command
writes to a path you choose.

The commands work on any OpenDocument file, a ZIP package (`.odt`, `.ods`, `.odp`, `.odg`,
templates, …) or a flat XML file (`.fodt`, `.fods`, …); the file's declared media type, not
its extension, decides what it is. Text documents and spreadsheets get the full workflow
below. Other kinds get the common checks (package, kind, version, metadata, schema), `audit`
notes with `ODF009` that no semantic audit exists for their family yet, and the common
`[document]` decisions can still be applied; see
[Architecture](ARCHITECTURE.md#document-families).

## 1. Establish the baseline

```bash
uv run --no-sync odfa11y audit original.odt --schema --format json > before.json
uv run --no-sync odfa11y styles original.odt
```

An audit is read-only. Findings name a rule, a [location](RULES.md#locations) and, where a configuration can
address them, a `remedy`: the key that holds the decision. `--schema` also validates
every member against the bundled official ODF schema for the declared version
(1.3 or 1.4); see [Accessibility and limits](ACCESSIBILITY.md#odf-schema-validation).
Audit accepts several files and detects PDF by content, so
`odfa11y audit a.odt b.pdf` reports both.

Open the original in Writer and identify its intended heading hierarchy, language,
data-table headers, meaningful graphic descriptions and intentional page breaks. These
decisions cannot be inferred from appearance.

## 2. Record the decisions

```bash
uv run --no-sync odfa11y template original.odt > document.toml
```

The template lists the open decisions with every line commented out, including the
fingerprint of each object it suggests. Uncomment and complete only what you have decided;
see [Configuration](CONFIGURATION.md). The template refuses a document it cannot read well
enough to plan (blocking findings on stderr, status 2) rather than printing an empty plan.
Then:

```bash
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml --dry-run
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml
```

Each target reports `applied`, `unchanged` or `failed`. Any failure (a table or graphic
that does not exist, a header count that conflicts, an invalid language) aborts the run
and writes nothing. Before publishing, the executor also checks that visible text is
unchanged (apart from counted spacer removals) and that the ODF schema shows no
violation the source did not already have; for a spreadsheet the guard compares every sheet
name's position and every non-empty cell's text, so only sheet names may differ. A plan
written for another family (a `[text]` table applied to a spreadsheet, a `[spreadsheet]`
table applied to a text document) is refused outright. Publication is atomic.

## 3. Export and check the PDF

With LibreOffice 26.8 or newer installed (`soffice` or `libreoffice` on `PATH`, or `--soffice PATH`):

```bash
uv run --no-sync odfa11y export reviewed.odt reviewed.pdf
uv run --no-sync odfa11y audit reviewed.pdf --strict
uv run --no-sync odfa11y audit reviewed.pdf --verapdf --strict
```

`--verapdf-path PATH` names the validator executable and implies `--verapdf`.

Before relying on a LibreOffice installation for documents with hyperlinks, run
`uv run --no-sync odfa11y doctor`. Its `pdfua_link_descriptions` line says whether that
LibreOffice exports link descriptions (`supported`) or whether every hyperlink will be
reported as `PDF019` (`unsupported`); see [Accessibility](ACCESSIBILITY.md).

The exporter uses a temporary LibreOffice profile, requests PDF/UA-1 and tagged PDF, and
publishes the PDF atomically. The built-in PDF audit is a fast smoke test of metadata,
tagging and structure (roles, headings, lists, tables, figures, links). `--verapdf` runs
the authoritative PDF/UA-1 validator and reports each failed rule with its clause and
test number. If veraPDF cannot be found the report contains the warning `VERA000`;
`--strict` makes that fail.

Writer hyperlinks require an explicit meaningful **Name** (`office:name`). The doctor
self-test checks a named link; an unnamed link fails PDF/UA-1 validation. See
[link descriptions](ACCESSIBILITY.md#link-descriptions).

## 4. Compare the renders

```bash
uv run --no-sync odfa11y compare original.odt reviewed.odt --diff-dir diffs
```

Both documents are exported (only families with a PDF export can be) with the same LibreOffice and profile, then compared by page
count and size, text, links and rendered ink; see [Fidelity](FIDELITY.md). Renaming a
sheet changes the name Calc's default page header prints, so the comparison reports it as
a text difference (`FID003`) unless the header is changed first; see
[spreadsheet PDF exports](ACCESSIBILITY.md#spreadsheet-pdf-exports). `compare`
also takes two PDFs directly.

## 5. Or do it all, with evidence

```bash
uv run --no-sync odfa11y pipeline original.odt --config document.toml \
  --output-dir evidence --profile production
uv run --no-sync odfa11y check-evidence evidence
```

An **assurance profile** names the stages a run requires and how strictly it gates; the
effective profile is recorded in `run.json`.

| Profile | Stages | Gating |
| --- | --- | --- |
| `inspect` | identify, audit, remediate, audit the result | warnings do not fail |
| `verify` (default) | `inspect` plus export, PDF audit and fidelity comparison | warnings do not fail |
| `production` | `verify` plus veraPDF, which must be available | warnings fail (strict) |

The pipeline runs the stages in order and stops at the first failed gate; later stages are
recorded as `skipped`. A stage the document's family does not have (PDF export for a family
without a PDF filter) is `not-applicable`, which is not a failure, except under `production`, which requires PDF
validation and therefore fails for such a document. The
[evidence directory](EVIDENCE.md) is published whether the run passed or failed, even when
the source cannot be read.

## Exit statuses

| Status | Meaning |
| --- | --- |
| `0` | Success; warnings are allowed without `--strict`. |
| `1` | A report has warnings and `--strict` was supplied. |
| `2` | A report has errors (also argparse's status for invalid arguments), `template` could not read the document, or `check-evidence` found problems. |
| `3` | An execution failure: invalid configuration, failed remediation, missing or failing external tool, unreadable input. The message is on stderr. |

For several reports the highest status wins. Informational findings never fail a command.

| Symptom | Action |
| --- | --- |
| Unknown TOML key or wrong type | Compare the field with [Configuration](CONFIGURATION.md); use unquoted booleans and positive integer header counts. |
| `remediate` lists failed targets | Fix the named table, graphic key or header count; a selector that matches nothing is an error. |
| "Remediation introduced ODF schema violations" | The operation produced markup the ODF schema rejects; the message lists the violations. |
| `PDF019` | Give the Writer hyperlink a meaningful Name before export; check existing references before renaming it. |
| `pdfua_link_descriptions: unsupported` | The supported runtime failed its named-link self-test; inspect the exporter installation. |
| LibreOffice version rejected | Install LibreOffice 26.8 or newer; unidentifiable versions are also rejected. |
| LibreOffice executable not found | Install LibreOffice and expose its CLI on `PATH`, or pass `--soffice`. |
| `FID005` after spacing or spacer changes | Content moved. Review the diff images; if the movement is intended set `fidelity.pagination = "may-change"`. |
