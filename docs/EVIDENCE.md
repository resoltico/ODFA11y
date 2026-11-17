# Evidence bundles

Use `run --output-dir DIR` to retain decisions, stage outcomes and human-review needs.
A failed run can produce a valid bundle; integrity does not imply passing gates.

```text
manifest.json        SHA-256 of every other declared published file
run.json             immutable run record (schema_version = 1)
REVIEW.md            outstanding human work, observed checklist topics and facts
remediated.<ext>     when remediation guards produced a candidate
source.pdf           when source export completed
remediated.pdf       when candidate export completed
verapdf.xml          parsed validator XML, with diagnostic paths redacted
diff/                declared rendered difference images
```

The destination must be absent or empty. A temporary sibling publishes with one rename.
Completed artifacts survive later gate failures. Unsafe destinations or publication failures
can prevent publication. [Batch](BATCH.md) requires a new output root; item preparation errors
appear only in `batch.json`, without a fabricated run or an item bundle.

## Consume the record

Use the shipped [JSON Schemas](SCHEMAS.md). `run.json` records source identity, plan header,
answered decisions, fidelity policy, profile, typed stage outcomes, tool identities, schema
assurance, fonts and human-review topics. Unknown measurements remain null. Reports carry
producer-owned typed facts. Only doctor records contain capability experiments.

`plan_sha256` hashes canonical plan/decisions, fidelity policy and profile independently of
TOML formatting. The manifest owns all file hashes, including run/review files; there is no
run-record `outputs` hash map. Records have sorted keys and no timestamps. Native PDFs can
still have variable timestamps/IDs. Reported tool versions do not authenticate executables.

A stage executes when its declared inputs exist. Candidate findings do not block its PDF
export; validator failure does not block fidelity. A source audit that cannot establish
readability supplies no remediation/export input. A refused candidate is never exported.

## Privacy

Diagnostic artifacts redact known source/capture/work/output/profile locations and other
local directories before JSON/XML serialization and Markdown escaping. Validator XML is a
redacted diagnostic report, not a raw-byte transcript. Original report bytes are parsed
without replacement decoding. In-memory diagnostics are not universally path-free.
Review sheets display dynamic names, metadata, findings and diagnostics as literal Markdown
text after redaction; authored HTML, images and links do not become active review content.
ODF/PDF/image payloads and authored wording/references can retain private content. Treat
bundles with the source's confidentiality; do not attach private bundles to public issues.

## Source capture

Every use case captures each source once in a private temporary directory, never beside
the user's file. Its digest, original identity and opened document are reused. Aliases
resolve first; the opened descriptor must match the selected device/inode. Nonregular or
substituted files refuse before reading. POSIX uses anti-symlink open where available;
Windows also checks descriptor identity.

Capture permits at most 256 MiB of physical bytes, checked before/during copy, separately
from ZIP's declared-uncompressed budget. Changes to size/mtime during capture refuse.
Owned partial files are removed on failure/interruption. Source directories need no write
access. Original input bytes are not themselves a declared evidence artifact.

Source and ancestor namespaces must remain stable during selection. Capture does not fetch
or rewrite dependencies or isolate the network. Private native export refuses filename/path
fields and relative hyperlink destinations, including XML-base cases. Use absolute link
destinations or source-only inspection/remediation. See
[native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies).

## Verify recorded files

```sh
uv run --no-sync odfa11y verify-evidence evidence
```

The manifest has exactly `{"bundle_version": 1, "files": {…}}`, with normalized relative
paths and 64-hex digests. Missing, modified, unlisted, unsafe, linked or special files produce
status 2. Only root `manifest.json` is exempt; nested manifests are ordinary data.
Listed components are traversed without following links outside the bundle.

Verify a stable directory whose ancestors cannot be replaced during inspection. Someone
able to rewrite the bundle can rewrite its manifest: hashes establish recorded-file
integrity, not authenticity, accessibility or review quality. Native rendering is compared
within a run; cross-machine pixel identity is not claimed.

Run records carry the typed ODF detection result in `document`, including its layout and
structured kind/family. Captured identity is recorded separately as `source_name` and `source_sha256`.
