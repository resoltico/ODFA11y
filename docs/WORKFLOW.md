# Document workflow

Use the locked environment from the [README](../README.md#start-here).
Keep the original file and use distinct output paths: destinations can be
replaced. ODFA11y does not provide a transaction across ODT and PDF outputs.

## 1. Establish the baseline

```bash
uv run --no-sync odfa11y audit original.odt --format json > before.json
uv run --no-sync odfa11y styles original.odt
```

An audit is read-only. Findings identify package errors, missing semantics and
review items. The style report shows effective spacing and use counts; it does
not decide which style a paragraph ought to have.

Open the original in Writer. Identify its intended heading hierarchy, document
language, data-table headers, meaningful graphic descriptions and intentional
page breaks. These decisions cannot be inferred reliably from appearance alone.

For schema validation, obtain the main and manifest Relax NG schemas from the
[official OASIS ODF 1.4 schema directory](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/schemas/).
Pass local paths; ODFA11y does not download or vendor schemas:

```bash
uv run --no-sync odfa11y audit original.odt \
  --schema schemas/OpenDocument-v1.4-schema.rng \
  --manifest-schema schemas/OpenDocument-v1.4-manifest-schema.rng
```

The main schema covers content, styles, metadata and settings when present. The
manifest uses its separate schema. A changed version declaration is not evidence
that the complete document conforms to the declared version.

## 2. Apply reviewed choices

Create `document.toml` from the [configuration example](CONFIGURATION.md#example):

```bash
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml
```

Review the printed changes. Unmatched graphic or table names are skipped. Image
descriptions and header choices remain your responsibility. The `fixable` field
in an audit is a hint; it does not mean that all necessary choices are known or
that a repair will run automatically.

For spacing changes, first inspect `styles`, choose a reference paragraph and
select only the affected styles:

```bash
uv run --no-sync odfa11y normalize-spacing reviewed.odt spaced.odt \
  --reference-text 'Text from the reference paragraph' \
  --target-style BodyTight
```

Reference matching uses a substring by default; `--exact-reference` requires an
exact match. Repeat `--target-style` for additional styles. Headings are targets
only with `--include-headings`. The first matching reference is used, so choose
text that uniquely identifies the intended paragraph.

Use `spaced.odt` for subsequent steps if you applied spacing changes.
Blank-spacer removal is opt-in; review [its selection and preservation boundaries](ACCESSIBILITY.md#spacer-removal) before enabling it.

## 3. Re-audit and inspect the result

```bash
uv run --no-sync odfa11y audit reviewed.odt --strict --format json > after.json
```

Include the schema options here if schema validation is part of your acceptance
process. Inspect page appearance, pagination and semantics in Writer before
proceeding. The text guard compares normalized block text; it does not guarantee
an unchanged layout or identical whitespace.

## 4. Export and check the PDF

Install [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/)
and ensure `soffice` or `libreoffice` is on `PATH`:

```bash
uv run --no-sync odfa11y export-pdfua reviewed.odt reviewed.pdf
uv run --no-sync odfa11y verify-pdf reviewed.pdf --strict
```

The exporter uses a temporary LibreOffice profile, requests PDF/UA-1 and tagged
PDF, and enables document-title display and bookmarks. An export succeeding does
not prove conformance. `--soffice /path/to/soffice` selects an executable;
`--timeout` controls the standalone export timeout in seconds.

With [veraPDF](https://docs.verapdf.org/install/) and its supported Java runtime
installed:

```bash
uv run --no-sync odfa11y verify-pdf reviewed.pdf --strict --verapdf
```

Use `--verapdf /path/to/verapdf` to select an executable. ODFA11y requests the
`ua1` profile and reads XML compliance reports. If automatic lookup cannot find
veraPDF, the report contains the warning `VERA000`; `--strict` makes that warning
fail the command. A clean structural report without veraPDF does not establish
full machine-verifiable PDF/UA conformance.

Inspect reading order, heading/table navigation, link purpose, image descriptions,
contrast and text usability before delivery. Keep the edited ODT, distributed PDF
and reports together when an evidence trail is required.

## Combined commands

Audit an ODT and its existing PDF together:

```bash
uv run --no-sync odfa11y verify reviewed.odt --pdf reviewed.pdf --strict --format json
```

`verify` and `pipeline` emit a JSON array of reports; `audit` and `verify-pdf`
emit a single report object. A report's `passed` field means it has no error
findings. It can still contain warnings and does not change when `--strict`
changes the exit status.

For already reviewed inputs, the convenience pipeline combines the operations:

```bash
uv run --no-sync odfa11y pipeline original.odt reviewed.odt \
  --config document.toml --pdf reviewed.pdf --strict
```

The pipeline stops before export when its ODT audit contains errors, or warnings
with `--strict`. It emits the ODT report and retains the remediated ODT, but does not
create a new PDF. If a later step fails, earlier outputs may remain; use staged
commands when human acceptance must happen between steps. Export timeouts are configurable on `export-pdfua`, not on
`pipeline`.

## Exit statuses and troubleshooting

| Status | Meaning |
| --- | --- |
| `0` | Command succeeded, or audit has no errors; warnings are allowed without `--strict`. |
| `1` | Audit has warnings and `--strict` was supplied. |
| `2` | Audit has errors; argparse also uses this status for invalid CLI arguments. |
| `3` | A handled execution/configuration/export failure. |

For multiple reports, the largest audit exit status is returned. Informational
findings do not fail an audit. Successful remediation alone is not an audit pass.

| Symptom | Action |
| --- | --- |
| Unknown TOML key or incorrect type | Compare the field with [Configuration](CONFIGURATION.md); use unquoted booleans and positive integer header counts. |
| LibreOffice executable not found | Install LibreOffice and expose its CLI on `PATH`, or supply `--soffice`. |
| veraPDF unavailable | Install its CLI and Java prerequisites, or supply the executable path; inspect `VERA000`. |
| Schema load/validation error | Check local paths and the complete official schema files; inspect `ODF900`/`ODF901` details. |
| Text-preservation abort | Keep the original; inspect the requested change. Only counted empty-block removals are permitted; meaningful text changes remain rejected. |
| `PDF000` | The PDF cannot be opened or strictly parsed; inspect the file and exporter output. |

`uv run --no-sync odfa11y doctor --format json` records Python/library versions,
LibreOffice availability/version and the veraPDF path. It does not verify that all
external tools function, and it does not report the veraPDF version.
