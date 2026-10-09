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

Pipeline input is captured once beside the resolved source, following ordinary file aliases.
After resolving deliberate file/directory aliases, capture retains the selected device/inode
identity. The opened descriptor must be that same regular file; substitutions and nonregular
sources (including FIFOs) are refused before capture creation or reading. POSIX uses
anti-symlink open where available, plus the identity comparison; the latter also covers
regular-file replacement and uses Python's stat/fstat identity on Windows. Physical capture is limited to **256 MiB**, independently of the
ZIP parser's 256 MiB declared-uncompressed budget. The physical limit includes ZIP headers,
filenames, extra fields and padding and can reject a package whose declared payload would
fit the parser budget. Size is checked before copying and on the descriptor, and a bounded
copy also rejects growth. Capture refusal is an `identify-source` execution failure (status
3), with failure evidence when its destination remains writable. Partial owned copies are
removed on errors and ordinary interruption. This does not impose an OS memory/time sandbox
on arbitrary filesystems.

The source/staging directories must permit private temporary files and their caller-controlled
ancestor namespaces must remain stable for the whole capture/export lifetime. Leaf-file
identity does not establish parent/resource-directory identity: a parent exchange, even with
a hard link to the same file, can change the export base. Renaming a parent during copying
can invalidate the owned copy's pathname and defeat pathname cleanup. Such concurrency is
unsupported; use a stable isolated workspace. Concurrent in-place writes are also outside
the identity guarantee. Under the stable-namespace prerequisite, owned cleanup applies.
 Both baseline and candidate native
exports use private copies in that same resolved directory; the candidate copy has exactly
the validated artifact's bytes. The original display name remains separate from capture
identity, and the digest identifies the captured bytes every stage processes. Capture and declaration
preflight do not copy, rewrite or fetch external resources; native tools are not network-isolated. These known native limitations are reported
by the source audit:

- `ODF012`: a recognized resource declaration is external, unresolved, addressed with the
  wrong target shape, governed by an unestablished explicit XML base, or declares unestablished
  dynamic loading/execution. The authoritative element/attribute/target policy lives in
  [content/export_context.py](../src/odfa11y/content/export_context.py). It includes fill/bullet,
  chart-symbol, SVG definition/font and form-image-data references, even unused declarations.
  File targets need an exact non-directory member; directory separators remain meaningful
  after percent decoding. `draw:object` can address a separate file or a subdocument folder
  containing `content.xml`; OLE targets require a file or inline data. Chart self-data `.`
  has its own contextual meaning; parent-data `..` (also the omitted-attribute default) is unestablished at this scanned
  boundary. Flat URI resources cannot rely on package members. Native application export/compare
  refuse these dependencies; source-only `inspect` and remediation remain available.
- `ODF013`: authored filename/full-path fields require logical original identity. Native
  pipeline export refuses them because the current exporter would substitute private capture
  names. `inspect` preserves the fields; direct original export can use the actual original
  identity. Authored fields are not frozen or removed, and comparison still rejects a real
  visible change caused by a deliberately different final filename.

Ordinary navigational hyperlinks are distinct from automatic rendering dependencies. Their
references remain authored and are resolved by the native application against the controlled
input directory/base. Relative navigation can change when the published document is moved;
a copied ODF is not a self-contained bundle of external targets. An unresolved dependency is
not established preservation just because both PDFs omit it. Embedded assets also require
output/human review: presence, an image count or equal renders alone cannot prove the intended
asset was loaded or decoded correctly. The preflight covers known declarations in
content/styles/meta, including auto-reload replacement documents. Template provenance,
operated form-button/image links, form submission and normal text/drawing/image-map
navigation are distinct from image data. Declared applet code/base/archive, script/event
code and form data connections remain unestablished and are refused; this is not a claim
that every declaration executes or fetches. Embedded subdocument internals, opaque payloads,
inline execution, dynamic importer behavior and OS isolation remain outside this scan.
It does not establish universal importer isolation. Captures are removed and are not original-input
copies in the evidence bundle.

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
