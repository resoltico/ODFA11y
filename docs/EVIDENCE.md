# Evidence bundles

`pipeline --output-dir DIR` records automated decisions, their tools/results and required
human review. A bundle can represent failure; integrity does not mean passing gates.

```text
manifest.json        SHA-256 of every other file
run.json             published run record
REVIEW.md            gates, findings and human-review checklist
remediated.<ext>     when remediation passed; retains the source extension
source.pdf           when original export completed
remediated.pdf       when candidate export completed
verapdf.xml          when validator output exists; diagnostic values are redacted
fidelity/            generated diff images
```

The destination must be absent or empty. A temporary sibling is published with one rename,
so a bundle is not exposed half-written. Completed artifacts survive later gate failures;
unsafe destinations/publication failures can prevent evidence publication.

## run.json

The run record uses format 3; embedded reports use format 6. Published JSON has sorted keys,
no timestamps and redacted diagnostic paths. Fields include:

- `odfa11y`, `python`, `platform`, `libraries` and locale `environment`.
- `toolchain`: typed `libreoffice`/`verapdf` identities and `capabilities`; text export's
  `pdfua_link_descriptions` capability verdict. Its synthetic probe runs once at first
  export; files are excluded. Inspect-only/adapters without that probe do not measure it.
- `schemas`: bundled schema SHA-256 values; `export_options`: requested native options.
- `document`: displayed filename/digest and readable kind, media type, layout, family,
  adapter and declared ODF version. The digest is null when bytes could not be captured/hashed;
  successfully captured malformed ODF can retain its digest.
- `plan_sha256`: canonical operations, fidelity policy and profile together, independent
  of TOML formatting; `operations`, `fidelity_policy` and effective `profile`.
- `stages`: identify/audit source, remediate/audit result, export source/candidate, audit
  PDF, veraPDF and fidelity. Each is `passed`, `failed`, `skipped` or `not-applicable`,
  with reason, bounded diagnostic details and applicable reports/outcomes.
- `fonts`: source/candidate PDF fonts and embedding; `human_review`: family checklist.
- `outputs`: digests of retained stage artifacts, excluding generated `run.json`,
  `REVIEW.md` and `manifest.json`; `status`, `failed_stage` and `exit_status` describe the run.

Reports expose registered, typed, namespaced `facts`, not arbitrary metadata. Unknown
identity fields are explicitly null. Remediation records carry a structured `schema`
status/version and before/after/new violation counts. Draft 2020-12 contracts ship
offline in [the package schema resources](../src/odfa11y/schemas).

The manifest separately hashes **every other published file**, including `run.json` and
`REVIEW.md`. The two inventories avoid hashing a record through its own output digest.

`audit-source` informs remediation unless unreadable; `audit-remediated` gates the result.
Outside-profile stages are skipped, never passed. Required veraPDF absence fails
production. Native executable digests/signatures are not recorded; reported versions do
not establish executable authenticity. For batch invalid plans, failure evidence adds
`load-plan`; see [Batch](BATCH.md).

## No local paths

Published diagnostic records and designated report artifacts are redacted. Known source,
work, output and profile directories become `<source>`, `<work>`, `<output>`, `<profile>`;
other path directories become `<path>`. XML/JSON values are redacted before serialization,
preserving syntax. `write_bundle` callers designate report names through `diagnostics`;
other artifacts copy byte-for-byte regardless of suffix. Pipeline designates `verapdf.xml`
as diagnostic XML, so it is not a byte-raw validator transcript.

The in-memory API result and ordinary local text/JSON diagnostics are not universally
path-free. Documents, PDFs, images and quoted content can retain private data or authored
paths. Treat a bundle with the source's confidentiality; do not attach private bundles to
public issues. The original ODF is not copied into evidence, but its candidate/PDF content
can reproduce sensitive material. Capture ownership and identity are defined below.

## Source capture

Pipeline captures input once beside the resolved source. Deliberate file/directory aliases
resolve first, then the opened regular-file descriptor must match the selected device/inode
identity. Substitution/nonregular sources (including FIFOs) refuse before capture creation
or reading. POSIX uses anti-symlink open where available; stat/fstat identity also applies
on Windows. Concurrent in-place writes are outside this identity guarantee.

Physical capture is capped at **256 MiB**, separate from the ZIP declared-uncompressed
budget. ZIP headers, names, extra fields and padding count. Checks occur before copying,
on the descriptor and during bounded copy to reject growth. Refusal is an
`identify-source` execution failure (status 3), with failure evidence when writable.
Owned partial copies are removed on errors/ordinary interruption under the directory
prerequisite below.

Source/staging directories must allow private files and their caller-controlled ancestor
namespaces must remain stable throughout capture/export. Leaf identity does not protect
parent/resource-directory exchange, even if a hard link retains the same leaf. A renamed
parent can invalidate capture paths and cleanup; use a stable isolated workspace. There is
no OS memory/time sandbox for arbitrary filesystems.

Baseline/candidate native exports use private copies in the resolved source directory;
the candidate copy has exactly the validated artifact's bytes. Display name remains separate
from capture identity; the recorded digest identifies captured bytes. Private captures are
removed and are not original-input artifacts in evidence.

Capture does not copy/rewrite/fetch dependencies or isolate the network. Guarded native
work refuses unresolved declarations (`NATIVE001`) and captured filename/path-sensitive content
(`NATIVE002`). Direct original export/comparison can retain logical identity. See the canonical
[native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies) and
[formula policy](ACCESSIBILITY.md#formula-declarations). Relative navigation remains authored
and may change when a published ODF moves; the candidate is not a bundle of external targets.
Raw `pdf.export_pdfua()` callers own policy and isolation; see [API](API.md).

## REVIEW.md

The review sheet separates automated gate outcomes and established facts from required human
review. It distinguishes veraPDF not run, execution failure and validation failure. When
veraPDF did not pass, it states that built-in checks are not PDF/UA validation. Semantic
review is never turned into a machine pass.

## Verifying

```bash
uv run --no-sync odfa11y check-evidence DIR
```

Missing, modified and unlisted files yield status 2. The untrusted manifest must be exactly
`{"format": 1, "files": {…}}`, with normalized relative names and 64-hex digests: no absolute
or drive-qualified paths, `.`/`..`, backslashes or controls. Verification rejects symbolic
links/special files and traverses listed components without following links outside the
bundle. Only root `manifest.json` is exempt from inventory; a nested one is ordinary data.

The bundle **and ancestor namespace must remain stable throughout verification**. Verify a
copy nobody is writing to; concurrent hostile directory replacement is outside the contract.
Hashes establish integrity against the recorded manifest, not authenticity, accessibility
or review quality. Someone able to rewrite the directory can also rewrite the manifest.

## Reproducibility

Equivalent inputs, plan and toolchain give equal stages/operations and byte-identical
remediated documents. Native PDF timestamps/IDs can make PDF hashes differ across runs.
Rendering is compared on one machine/run; cross-machine pixel identity is not claimed.
