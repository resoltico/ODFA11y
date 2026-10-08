# Evidence bundles

`pipeline --output-dir DIR` publishes one directory that lets someone who was not there
see what was changed, with which tools, and what a person must still decide.

```
manifest.json        SHA-256 of every other file
run.json             the complete run record
REVIEW.md            gates, facts, findings and the human-review checklist
remediated.<ext>     only when remediation passed; keeps the source's extension
source.pdf           LibreOffice export of the source
remediated.pdf       LibreOffice export of the remediated document
verapdf.xml          raw veraPDF report, when veraPDF ran
fidelity/            diff images for pages that differ
```

The directory must not exist or must be empty. It is built in a temporary sibling and
published with one rename, so it is never half-written; a failed run still publishes its
evidence. Artifacts are retained for stages that completed, including the remediated
document when remediation passed even if a later gate failed.

## run.json

Format 2. Sorted keys, no timestamps and no local directories in diagnostic values:

- `odfa11y`, `python`, `platform`, `libraries` and the locale `environment`;
- `toolchain`: LibreOffice and veraPDF names and reported version numbers.
  Text exports also record `pdfua_link_descriptions`, measured with an explicitly named
  synthetic link. The probe runs once at the first export; its files are excluded.
  Inspect-only profiles and adapters without a probe do not measure it;
- `schemas`: SHA-256 of each bundled ODF schema;
- `export_options`: the exact LibreOffice PDF export options;
- `document`: file name, SHA-256 (null when the file could not be read), and, when readable,
  `kind`, `media_type`, `layout` (`package` or `flat`), `family`, `adapter` and `odf_version`;
- `plan_sha256`: digest of the operations, fidelity policy and profile together, independent
  of how the configuration file was formatted;
- `profile`: the effective assurance profile (stages, strictness, veraPDF requirement);
- `operations` and `fidelity_policy`: the effective configuration;
- `stages`: in order `identify-source`, `audit-source`, `remediate`, `audit-remediated`,
  `export-source`, `export-remediated`, `audit-pdf`, `verapdf`, `fidelity`, each `passed`,
  `failed`, `skipped` or `not-applicable` with its reason, bounded diagnostic details,
  report and remediation outcomes;
- `fonts`: the fonts of the source and remediated PDFs, with whether each is embedded;
- `human_review`: the family's checklist, as rendered in `REVIEW.md`;
- `outputs`: SHA-256 of every published artifact; `status` and `failed_stage`.

`audit-source` is informational (its errors are what remediation exists to fix) unless the
document cannot be read. A validator outside the profile is `skipped`, never `passed`; in
the `production` profile an unavailable veraPDF fails the run. Executable digests and
signatures are deliberately not recorded: a launcher script's digest says little about the
program behind it, and a hash proves integrity, not authorship.

### No local paths

Diagnostic records and explicitly designated report artifacts are redacted before publication.
Known source, work, output and profile directories become `<source>`, `<work>`, `<output>`
and `<profile>`; other path directories become `<path>`. XML/JSON values are redacted before
serialization, preserving valid syntax and escaping. `write_bundle` callers designate report
names with `diagnostics`; all other artifacts are copied byte for byte regardless of suffix.
Document/PDF/image payloads may retain authored paths and private content. `outputs` identifies
final staged artifact bytes, matching the published record and manifest; a hash does not prove
syntax validity, accessibility or review quality.

Pipeline input is captured once in a temporary file beside the original source to preserve
its relative-resource directory. Creating that file requires a writable source directory.
The original name remains the display identity; the source digest identifies the captured
bytes used by every stage. Concurrent in-place writes during capture may affect those bytes;
external dependencies are not captured and must remain stable in the caller's isolated
workspace. The captured input is removed and is not included in the evidence bundle.

## REVIEW.md

Separates *machine-established facts* (metadata, counts, schema and validator results,
fidelity measurements) from the *human review still required* checklist, and states
plainly when veraPDF did not run that the built-in PDF checks are not PDF/UA validation.
Nothing semantic is turned into a pass.

## Privacy

A bundle contains artifacts from completed stages: the remediated document, exported PDFs,
diff images and diagnostics that can quote document text. It does not copy the original ODF. Treat a bundle with the same confidentiality as the
document, and do not attach one to a public issue.

## Verifying

```bash
uv run --no-sync odfa11y check-evidence DIR
```

reports missing, modified and unlisted files (exit status 2 on any). The manifest is
treated as untrusted input: it must be exactly `{"format": 1, "files": {…}}` with
normalised relative names (no absolute or drive-qualified paths, no `.` or `..`, no
backslashes or control characters) and 64-hex digests, and each listed file is reached
component by component without following symbolic links, so a hostile bundle cannot make
the verifier read outside it. Symbolic links, special files and any file that is not listed
are reported, and only the root `manifest.json` is exempt from the inventory (a nested one
is just another unlisted file). Verify a copy nobody is writing to. The manifest proves
integrity against accidental change, not authorship: a person who can rewrite the
directory can rewrite the manifest too.

## Reproducibility

Re-running with the same inputs, configuration and toolchain gives equal stages and
operations and a byte-identical remediated document. PDF files embed exporter timestamps and
IDs, so their hashes can differ between runs.
