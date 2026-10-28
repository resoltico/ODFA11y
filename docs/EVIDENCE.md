# Evidence bundles

Use `pipeline --output-dir DIR` to retain decisions, stage results and human-review needs.
A failure can produce a valid bundle; integrity does not imply passing gates.

```text
manifest.json        SHA-256 of every other published file
run.json             typed run record
REVIEW.md            automated outcomes and required human review
remediated.<ext>     when candidate publication passed
source.pdf           when baseline export completed
remediated.pdf       when candidate export completed
verapdf.xml          available validator output, with diagnostic paths redacted
fidelity/            available rendered differences
```

The destination must be absent or empty. A temporary sibling publishes with one rename.
Completed artifacts survive later gate failures; unsafe destinations/publication failures
can prevent evidence publication. [Batch](BATCH.md) requires a new output root.

## Consume the record

Use the shipped [JSON Schemas](SCHEMAS.md). `run.json` records source identity, plan header,
answered decisions, explicit rebind, operations, policy/profile, stages, tool identities,
scoped capability results, schema assurance, fonts, outputs and required human review.
Unknown identities remain null. Reports carry registered typed facts.

`plan_sha256` hashes canonical plan/decisions, operations, fidelity policy and profile,
independently of TOML formatting. `outputs` identifies stage artifacts; the manifest also
hashes the generated run/review files, avoiding a self-reference. Published records have
sorted keys and no timestamps. Native PDFs can still have variable timestamps/IDs.
Reported tool versions do not authenticate executables.

## Privacy

Designated diagnostics redact known source/work/output/profile directories and other path
directories before JSON/XML serialization. Validator XML is a redacted diagnostic report,
not a byte-raw transcript. In-memory/local diagnostics are not universally path-free.
ODF/PDF/image payloads and authored wording/references can retain private content. Treat
bundles with the source's confidentiality; do not attach private bundles to public issues.

## Source capture

Planning, remediation and pipeline audits bind to bounded private regular-file captures.
Pipeline captures beside the resolved source and uses those exact inspected bytes for
binding and execution. Aliases resolve first; opened descriptor device/inode identity must
match the selected file. Nonregular/substituted files refuse before reading. POSIX uses
anti-symlink open where available; Windows also checks descriptor identity.

Capture permits at most 256 MiB of physical bytes, checked before/during copy, separately
from ZIP's declared-uncompressed budget. Owned partial files are removed on ordinary
failure/interruption. Baseline/candidate native copies retain their logical source-directory
context and are removed afterward; original input bytes are not an evidence artifact.

Source, staging and ancestor namespaces must remain stable and writable for private files.
Leaf identity does not protect parent/resource-directory exchange or concurrent in-place
writes. Capture does not fetch/rewrite dependencies or isolate the network. Captured
filename/path-sensitive export refuses; direct original export/comparison can retain
identity. See [native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies).

## Verify recorded files

```sh
uv run --no-sync odfa11y verify evidence
```

The manifest must be exactly `{"format": 1, "files": {…}}`, with normalized relative paths
and 64-hex digests. Missing, modified, unlisted, unsafe, linked or special files produce
status 2. Only root `manifest.json` is exempt; nested manifests are ordinary data.
Listed components are traversed without following links outside the bundle.

Verify a stable directory whose ancestors cannot be replaced during inspection. Someone
able to rewrite the bundle can rewrite its manifest: hashes establish recorded-file
integrity, not authenticity, accessibility or review quality. `REVIEW.md` keeps human
acceptance separate from automated checks. Native rendering is compared within a run;
cross-machine pixel identity is not claimed.
