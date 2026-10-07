# Evidence bundles

`pipeline --output-dir DIR` publishes one directory that lets someone who was not there
see what was changed, with which tools, and what a person must still decide.

```
manifest.json        SHA-256 of every other file
run.json             the complete run record
REVIEW.md            gates, facts, findings and the human-review checklist
remediated.odt       only when remediation passed
source.pdf           LibreOffice export of the source
remediated.pdf       LibreOffice export of the remediated ODT
verapdf.xml          raw veraPDF report, when veraPDF ran
fidelity/            diff images for pages that differ
```

The directory must not exist or must be empty. It is built in a temporary sibling and
published with one rename, so it is never half-written; a failed run still publishes its
evidence (and no `remediated.odt`).

## run.json

Sorted keys, no timestamps and no absolute paths:

- `odfa11y`, `python` and `platform` versions;
- `toolchain`: LibreOffice and veraPDF names and versions as the tools report them
  (`unknown` when a tool will not say);
- `schemas`: SHA-256 of each bundled ODF schema;
- `export_options`: the exact LibreOffice PDF export options;
- `input`: file name and SHA-256 of the source;
- `operations` and `fidelity_policy`: the effective configuration;
- `stages`: in order `audit-source`, `remediate`, `audit-remediated`, `export-source`,
  `export-remediated`, `audit-pdf`, `verapdf`, `fidelity`, each `passed`, `failed` or
  `skipped` with its reason, report and remediation outcomes;
- `outputs`: SHA-256 of every published artifact; `status` and `failed_stage`.

`audit-source` is informational (its errors are what remediation exists to fix) unless the
package cannot be read. An unavailable or unrequested validator is `skipped`, never
`passed`; with `--strict` an unavailable requested veraPDF fails the run.

## REVIEW.md

Separates *machine-established facts* (metadata, counts, schema and validator results,
fidelity measurements) from the *human review still required* checklist, and states
plainly when veraPDF did not run that the built-in PDF checks are not PDF/UA validation.
Nothing semantic is turned into a pass.

## Privacy

A bundle contains copies of the input document, its remediated ODT, both PDFs and diff
images, and reports quote document text. Treat a bundle with the same confidentiality as the
document, and do not attach one to a public issue.

## Verifying

```bash
uv run --no-sync odfa11y check-evidence DIR
```

reports missing, modified and unlisted files (exit status 2 on any). The manifest proves
integrity against accidental change, not authorship: a person who can rewrite the
directory can rewrite the manifest too.

## Reproducibility

Re-running with the same inputs, configuration and toolchain gives equal stages and
operations and a byte-identical remediated ODT. PDF files embed exporter timestamps and
IDs, so their hashes can differ between runs.
