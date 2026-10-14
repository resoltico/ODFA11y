# Document workflow

Use the locked environment from the [README](../README.md#start-here). Keep the
original file: remediation refuses to write over its own source, and every command
writes to a path you choose.

The commands work on any OpenDocument file, a ZIP package (`.odt`, `.ods`, `.odp`, `.odg`,
templates, …) or a flat XML file (`.fodt`, `.fods`, …); the file's declared media type, not
its extension, decides what it is. Text, spreadsheet, presentation and drawing families have native PDF workflows. Formula
has native source semantics and an exporter whose current tagging failures remain gates.
Chart, Image and Base have source assurance only; production fails when required PDF
stages cannot run. See [family contracts](ARCHITECTURE.md#document-families),
[batch runs](BATCH.md) and [SARIF output](SARIF.md).

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
`odfa11y audit a.odt b.pdf` reports both. Text and JSON audits retain completed reports
and continue after unreadable inputs; stderr identifies each failed input and the command
returns execution status 3 even when other inputs pass. Failed inputs do not become clean
reports. JSON keeps the existing single-report object/multiple-report array shape.
SARIF instead preflights all identities and confinement before inspection; an execution
failure emits no partial SARIF log. Audit/compare accept regular files and ordinary file
aliases; nonregular inputs are refused without waiting for FIFO data.

Text audit and comparison output starts with the actual command outcome, exit status
and gate policy. Individual reports say `Check: no errors` or `Check: errors found`;
warnings remain visible and fail the command when `--strict` is enabled. Findings
precede metadata, and text wraps at 80 columns without splitting paths or identifiers.
Terminal controls in filenames, document fields and tool diagnostics appear as visible
escapes. JSON report `passed` still means no error findings. For JSON and SARIF,
`--strict` retains `Command gate (--strict): PASS/FAIL (exit N)` on stderr; machine
payloads and exit statuses are unchanged.

Every `COMMAND --help` includes examples. Running `odfa11y` without a command prints
the workflow help on stderr and exits 2; close command typos receive a suggestion
without executing it. Readable ODF reports with open decisions suggest a print-only
template command. Examples and copied command suggestions use POSIX shell quoting;
control-bearing filenames are displayed safely without a copyable command suggestion.
Configuration errors identify the existing plan and suggest editing it, rather than
overwriting reviewed decisions.

For text commands with interactive stderr, append-only progress lines show active
core stages, native work and evidence publication. Redirected stderr receives no
progress. JSON/SARIF commands never receive progress, even with interactive stderr;
redirecting stdout alone does not suppress text progress on interactive stderr.
A disconnected progress stream disables progress without stopping document work.

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

Dry runs label outcomes as proposed and write nothing. An empty plan explicitly says
that no operations were configured; uncomment only decisions you have reviewed.

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
LibreOffice exports the native `office:title` description (`supported`) or ignores that
field in the self-test (`unsupported`); see [Accessibility](ACCESSIBILITY.md).

The exporter uses a temporary LibreOffice profile, requests PDF/UA-1 and tagged PDF, and
publishes the PDF atomically. The built-in PDF audit is a fast smoke test of metadata,
tagging and structure (roles, headings, lists, tables, figures, links). `--verapdf` runs
the authoritative PDF/UA-1 validator and reports each failed rule with its clause and
test number. If veraPDF cannot be found the report contains the warning `VERA000`;
`--strict` makes that fail.

Native source link-description plans author `office:title` and preserve target Names.
The tested Writer exporter ignores that title; strict PDF failures remain visible. See
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
| `pdfua_link_descriptions: unsupported` | The native `office:title` self-test lacks PDF alternate text; source descriptions do not waive `PDF019`. |
| LibreOffice version rejected | Install LibreOffice 26.8 or newer; unidentifiable versions are also rejected. |
| LibreOffice executable not found | Install LibreOffice and expose its CLI on `PATH`, or pass `--soffice`. |
| `FID005` after spacing or spacer changes | Content moved. Review the diff images; if the movement is intended set `fidelity.pagination = "may-change"`. |

Missing veraPDF in a profile that requires it is an execution failure: failed stage
`verapdf`, exit status **3**, retained completed artifacts and skipped fidelity. Optional
`audit --verapdf` absence remains `VERA000` warning behavior (status 0 ordinarily, 1 with
`--strict`). Native dependency/captured-identity limits and capture failures are described
in [Evidence](EVIDENCE.md#no-local-paths); source-only inspection remains available.

## Formula declarations at native export

Guarded export and comparison inspect `style:condition`, `table:condition`,
`table:expression`, `table:formula` and `text:formula`, named expression/range declarations,
base/source range addresses, and reachable embedded ODF content/styles. They classify dependencies without evaluating
formulas or trusting cached results. Standard OpenFormula namespace prefixes (including
aliases) and unprefixed expressions are equivalent. The supported lexical subset includes
literals, ordinary operators/nested calls, bracketed local cell/range references and scoped
simple names; unsupported condition grammars such as `cell-content()` and other syntax
refuse explicitly. Names are case-insensitive and missing, ambiguous or cyclic declarations
cannot establish a clean context.

The function-name/query table is derived from ODF 1.4 Part 4, using the authoritative
source and digest recorded in the bundled `content/formula_data/functions.toml`; its 393
function names were independently compared with the standard's HTML headings. Runtime
processing never downloads this table. Unknown functions/namespaces and dynamic reference
construction (`INDIRECT`) refuse. Explicit external references and `DDE` are loading
limitations even inside branches that appear unreachable. `HYPERLINK` is navigation;
its nested arguments are still inspected. Function words inside quoted strings are inert.
`CELL("FILENAME")` and `INFO("directory")` depend on captured identity; direct original
export retains that identity, while pipeline captures refuse. Other standard literal
CELL/INFO queries are classified; dynamic or unsupported queries refuse.

Classification is bounded to 32,768 characters, 4,096 lexical tokens and depth 64 per
expression; named dependencies are inspected iteratively to avoid multiplying parser
recursion by the declaration graph. Named dependency expansions are capped at 4,096/depth 64, declaration
inspection at 100,000 per tree, and embedded object traversal at 64 directories, within
the existing XML/package budgets. Budget exhaustion is an incomplete-context refusal.
Reports reuse `ODF012`/`ODF013`, recording declaration/origin/incomplete counts without
formula literals or credentials. Auditing and source-only preservation remain available.
These declaration checks do not sandbox native tools or inspect opaque embedded internals;
callers retain responsibility for process isolation.
