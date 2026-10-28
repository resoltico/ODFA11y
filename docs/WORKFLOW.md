# Document workflow

Use the locked environment from the [README](../README.md#start-here). Keep the original:
remediation refuses its own source as destination. Commands accept packaged or flat ODF
according to declared media type. Native PDF stages depend on the
[family's capability](ACCESSIBILITY.md#document-families), not its extension.

Direct original export/comparison retain logical source identity. Pipeline export uses
private captures beside the source and refuses filename/path-sensitive content. Both guard
known native dependencies and require stable caller-controlled directories; see
[native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies) and
[source capture](EVIDENCE.md#source-capture). Guarded operations do not sandbox native tools.

## 1. Establish the baseline

```bash
uv run --no-sync odfa11y audit original.odt --schema --format json > before.json
uv run --no-sync odfa11y audit original.odt
```

Audit is read-only. Findings identify a rule, [logical location](RULES.md#locations) and,
typed open decisions requiring human answers. `--schema` validates recognized ODF parts and
native MathML against bundled schemas; it does not validate every arbitrary package member.
See [schema limits](ACCESSIBILITY.md#odf-schema-validation). `styles` is text-family inspection.

Audit accepts multiple files and detects PDF by content: `odfa11y audit a.odt b.pdf` checks
both. Text/JSON output retains completed reports and continues after unreadable inputs;
stderr identifies failures and exit status 3 takes precedence. A failed input is never an
empty clean report. JSON emits one object for one report, an array for multiple reports.
[SARIF](SARIF.md) preflights all source identities before inspection and emits no partial
log after execution failure. Audit/compare accept regular files and ordinary aliases;
nonregular inputs refuse without waiting for FIFO data.

Text audit/compare output begins with command outcome, exit status and gate policy.
Individual reports say `Check: no errors` or `Check: errors found`; warnings fail only
under `--strict`. JSON `passed` means no error findings. JSON/SARIF strict commands print
`Command gate (--strict): PASS/FAIL (exit N)` on stderr, keeping stdout machine-readable.
Terminal controls are escaped; text wraps at 80 columns without splitting identifiers.

Every command's `--help` includes examples. Invoking `odfa11y` without a subcommand prints help on stderr and exits 2. Close command
typos receive a suggestion without execution. Suggested commands use POSIX
shell quoting; control-bearing filenames receive no copyable command. Configuration errors
identify the selected plan and suggest editing it.

Interactive text stderr receives append-only progress for core/native/publication stages.
Redirected stderr and JSON/SARIF receive none. Redirecting stdout alone does not suppress
interactive text progress. A disconnected progress stream does not stop document work.

Open the source in its native application and decide intended structure, language,
descriptions, headers and page breaks. Appearance alone cannot establish these choices.

## 2. Record the decisions

```bash
uv run --no-sync odfa11y plan original.odt > document.toml
# edit document.toml: uncomment and complete only reviewed decisions
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan document.toml --dry-run
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan document.toml
```

Templates leave every decision commented out and include reviewed object fingerprints.
A source that cannot be inspected sufficiently yields blockers on stderr and status 2,
not a usable empty plan. See [Configuration](PLAN.md).

Targets report `applied`, `unchanged` or `failed`; dry runs label outcomes as proposed and
write nothing. A failed target, family mismatch, protected-content change or introduced
schema violation prevents publication. Multi-target operations validate their selections
before that operation edits. The executor publishes the whole candidate atomically after
content and available-schema guards; direct low-level operation calls have separate
[ownership](API.md). An empty plan explicitly reports no operations.

Signatures, encryption, tracked changes and excluded contexts impose
[preservation boundaries](ACCESSIBILITY.md#preservation-boundaries), including refusal
of signed-package remediation even for dry runs/no-op plans.

## 3. Export and check the PDF

With LibreOffice 26.8 or newer on `PATH` (`soffice`/`libreoffice`, or `--soffice PATH`):

```bash
uv run --no-sync odfa11y doctor
uv run --no-sync odfa11y export reviewed.odt reviewed.pdf
uv run --no-sync odfa11y audit reviewed.pdf --strict
uv run --no-sync odfa11y audit reviewed.pdf --verapdf --strict
```

Export uses a temporary LibreOffice profile, requests tagging/PDF/UA-1 and publishes
atomically. Export success does not establish PDF conformance. The built-in audit is a
structural smoke test; `--verapdf` runs machine-verifiable PDF/UA-1 rules. Each failure
retains the standard clause/test. `--verapdf-path PATH` implies validation. An unavailable
optional validator reports `VERA000`, a warning that fails with `--strict`.

Doctor's `pdfua_link_descriptions` probe measures native `office:title` support. A source
description never waives `PDF019`; inspect [link limitations](ACCESSIBILITY.md#link-descriptions),
[graphic roles](ACCESSIBILITY.md#graphic-roles) and the actual PDF.

## 4. Compare the renders

```bash
uv run --no-sync odfa11y compare original.odt reviewed.odt --diff-dir diffs
```

ODF inputs need an available family export filter; PDF inputs are compared directly and
can be mixed with ODF. Native renders use the same LibreOffice/profile. Comparison gates
extracted text and link targets, plus pages/ink under the [fidelity policy](FIDELITY.md).
A sheet rename can change Calc's printed header (`FID003`); see
[spreadsheet exports](ACCESSIBILITY.md#spreadsheet-pdf-exports).

## 5. Or do it all, with evidence

```bash
uv run --no-sync odfa11y pipeline original.odt --plan document.toml \
  --output-dir evidence --profile production
uv run --no-sync odfa11y verify evidence
```

| Profile | Required work | Gate |
| --- | --- | --- |
| `inspect` | Identify/audit source, remediate, audit result. | Errors fail; warnings allowed. |
| `verify` (default) | Inspect plus export, PDF audit and fidelity. | Errors fail; warnings allowed. |
| `production` | Verify plus required veraPDF. | Errors and warnings fail. |

The selected profile is recorded in `run.json`. Stages stop at the first failed gate;
later stages are `skipped`. Missing family capabilities are `not-applicable`, except that
production fails when required PDF proof is unavailable. Source audit findings inform
remediation; the remediated-source audit gates its result.

An [evidence bundle](EVIDENCE.md) retains completed artifacts and failures even for an
unreadable source, provided the destination remains safely writable. `verify`
checks recorded bytes, not accessibility, authenticity or human acceptance. See
[batch workflows](BATCH.md) for explicit independent document runs.

## Exit statuses

| Status | Meaning |
| --- | --- |
| `0` | Success; warnings allowed without strict gating. |
| `1` | Strict warning failure. |
| `2` | Error findings; plan blockers; bundle-integrity problems. |
| `3` | Execution failure: failed remediation, missing/failing required tool or unreadable input. |
| `4` | Invalid CLI arguments, plans or fidelity policies. |

Precedence is 3 > 4 > 2 > 1 > 0 across reports; informational findings never fail a command.
Required veraPDF absence fails stage `validate-pdf` with status 3, retaining completed artifacts
and skipping fidelity. Optional audit validation absence retains `VERA000` warning behavior.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Unknown TOML key/wrong type | Use [Configuration](PLAN.md); booleans are unquoted and header counts positive integers. |
| Failed remediation targets | Correct named selectors/counts or regenerate and review stale fingerprints. Nothing is published. |
| Introduced schema violations | Inspect listed violations; the operation's result fails the supported schema regression boundary. |
| `PDF019` | Inspect the exported link description. Existing Writer Names can matter, but renaming targets requires reference review. |
| Probe reports `unsupported` | Native `office:title` did not establish a PDF description; source success does not clear PDF failures. |
| LibreOffice rejected/unidentified | Install LibreOffice 26.8 or newer, expose its CLI, or select `--soffice`. |
| `NATIVE001` / `NATIVE002` | Read [native-context limits](ACCESSIBILITY.md#native-document-context-and-declared-dependencies); source-only inspect remains available. |
| `FID005` after deliberate movement | Review diffs; choose `fidelity.pagination = "may-change"` only if page/ink changes are intended. |
