# Changelog

Notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-10-09

### Breaking

- **Relative PDF URI links.** Comparison requires an explicit absolute catalog Base in a supported scheme; an unestablished relative context now refuses rather than claiming preservation. Author absolute URI targets or a supported Base. Only URI actions on Link annotations are compared, not every bookmark, launch action or hidden PDF reference; see [Fidelity](docs/FIDELITY.md).
- **Source audit warnings.** Recognized native-resource limitations now produce `ODF012`, and authored filename/path fields produce `ODF013`, with `native_export_limitations` report metadata. `audit --strict` can therefore exit 1 without exporting. Review the reported declarations and fields before strict audit or native export; source-only `inspect` retains them for review.
- **Pipeline capture.** Source directories must permit private temporary inputs beside the resolved source. Physical source/candidate capture is capped at 256 MiB independently of the ZIP declared-payload budget, so excessive headers/padding can be refused. Nonregular inputs and substitutions of the selected file are rejected before copying without waiting for FIFO data. Use a writable isolated workspace whose ancestor directories remain stable throughout processing; parent exchanges/renames and concurrent in-place writes are outside this guarantee.
- **Native export dependencies and identity.** Captured pipeline export refuses authored filename/path fields (`ODF013`). Guarded native export refuses recognized external, unresolved or unestablished declarations (`ODF012`), including unused fill/bullet, chart-symbol, SVG definition/font and form-image-data references. File targets need exact non-directory members; embedded ODF objects can address subdocument folders, while OLE targets need a file or inline data. Script/application execution, applet, nonempty named/IRI database/service/DDE bindings and auto-reload loading remain unestablished. Review/embed required assets in the native application or use source-only inspection. Direct original export retains filename/path identity but still refuses unsupported resource declarations. Ordinary navigation remains distinct, and moving an ODF output can change relative targets. This declaration preflight does not inspect all opaque embedded internals or sandbox native tools; caller-controlled OS/network/resource isolation remains necessary for untrusted inputs. See [native boundaries](docs/ACCESSIBILITY.md#native-document-context-and-declared-dependencies).
- **Evidence API and privacy.** `write_bundle` callers must designate redacted report artifacts with `diagnostics`; other artifacts retain their bytes regardless of suffix. Treat document/PDF/image payloads as private authored content that can contain paths; see [Evidence](docs/EVIDENCE.md).

### Added

- PDF audit enters invoked Form XObjects with stream-specific MCIDs, scoped resources and bounded nesting/reuse. Page/Form correspondence extends `PDF020`/`PDF021`; whole-object `/StructParent` ownership and unsupported cycles/depth/invocation work produce explicit incomplete-inspection refusal. This establishes inspected content correspondence and nonartifact graphic operations, not pixel visibility, reading order or PDF/UA conformance; see [PDF diagnostic limits](docs/ACCESSIBILITY.md#what-each-tool-establishes).
- Text/JSON multi-input audit retains completed reports and continues to later inputs after an unreadable file, identifying each failure on stderr and returning execution status 3. Failed inputs do not become clean reports. SARIF retains global identity/confinement preflight and no partial log on execution failure.

### Fixed

- Configuration and the public `FidelityPolicy` reject nonfinite raster tolerances, unknown pagination modes and invalid numeric types/ranges with `ConfigError` before export or comparison. Finite tolerances above 1.0 remain supported.
- Fidelity compares effective URI link destinations using direct/indirect catalog Base and action values, detecting Base-only destination changes and accepting equivalent relative/absolute targets. Query/fragment semantics, percent encoding and duplicate counts are retained; malformed URI components refuse, while valid IPv6 and encoded delimiters remain supported. Missing targets retain `FID004`, and added targets retain informational `FID006`.
- Unsupported PDF stream decoding and malformed decoder-parameter types produce structured `PDF000` audit refusal or controlled comparison execution failure without a traceback. Malformed annotation and descendant-font shapes also refuse rather than crashing or silently skipping inspection. CLI audit/compare reject nonregular inputs promptly, preserving ordinary regular-file aliases.
- Enormous positive DPI outside the renderer's numeric range is refused before float conversion. Representable DPI retains the existing 20-million-pixel budget and `FID007` refusal; no arbitrary small DPI maximum is added.
- Audit/compare show the effective `--strict` command gate on stderr without changing error-only `Report.passed` or structured report formats. Missing SARIF root advice names `--source-root` and containment requirements; help explains timeout units/defaults and `verify` versus required veraPDF validation with warning gates in `production`.
- Evidence publication preserves document payload bytes, redacts structured diagnostic values without corrupting XML/JSON and records final staged artifact hashes. Failed runs retain artifacts from completed stages, including a remediated document when a later gate fails. Evidence does not include a separate original ODF copy; retain the original input separately. Authored private content can remain in payloads.
- Audit and fidelity enforce the 64 MiB budget for unique consumed decoded page/Form, XMP, text CMap/encoding and applicable embedded Type1 data, plus a separate 64 MiB content-invocation work bound for tagged and untagged PDFs. Supported filter-output controls and stream/depth/invocation limits refuse incomplete inspection; they do not bound total peak memory or provide OS isolation.
- Shared marked-content references no longer hide multiple owners: `PDF022` counts incoming references through shared containers, while active-path cycle and traversal-work controls bound inspection.
- Pipeline stages process one captured source and record its digest separately from the original display identity. Baseline and validated candidate exports share the resolved source directory, including ordinary file aliases; the opened identity must match selection. Under the stable ancestor-namespace prerequisite, partial owned captures are cleaned on ordinary failure/interruption. Authored location fields remain unchanged in source-only work and are refused where staging cannot retain their identity.
- Unavailable required veraPDF produces failed stage `verapdf` and execution status 3; optional audit validation retains warning/strict-warning behavior.
- Standalone CLI commands and batch handle ordinary SIGINT/SIGTERM through scoped active-tool cleanup where the platform permits it, retaining completed evidence. Windows forced termination, SIGKILL and power loss can bypass cleanup/publication; there is no implicit recovery or automatic resumption. See [batch interruption](docs/BATCH.md).

### Internal

- Native compound Writer/Calc regression cases retain independent positive and stricter exporter-failure controls.
- CI bounds macOS LibreOffice provisioning to ten minutes and records verbose progress while retaining current-release selection and full native gates.
- CI pins stable veraPDF 1.30.3 with its reviewed SHA-256 alongside the exact version.
- PDF consumption uses the shared bounded scanner and reuses completed auxiliary-resource inspection.

## [0.5.0] - 2026-10-07

### Breaking

- **Plans and Python operations.** Graphic descriptions use `[text.graphics]` and
  `[spreadsheet.graphics]`, the shared `GraphicDescription`, and each family's
  `SetGraphicDescriptions`. Table decisions use `MarkTableHeaders` with structured
  `TableHeaders(rows, columns, fingerprint)` entries; integer TOML shorthand is rejected.
  Update imports and configuration to these contracts; no aliases or migration shims exist.
- **Finding locations.** Reports are format 4. Named targets use percent-encoded
  `[name=…]`, heading XML identities use `[id=…]`, and unnamed targets use plain ordinals
  such as `table[2]`. Update consumers to the grammar in [Rules](docs/RULES.md#locations).
- **Document metadata.** Supplied titles and descriptions must be nonblank. Omit fields
  to preserve existing metadata; clear metadata in the native application when intended.
- **Base media types.** Retired `application/vnd.oasis.opendocument.database` and
  `application/vnd.sun.xml.base` aliases are rejected. The standard Base media type is
  `application/vnd.oasis.opendocument.base`.

### Added

- **Presentation and drawing families.** Native Impress and Draw documents have separate
  page/shape audits, reviewed descriptions and complete navigation decisions in
  `[presentation]` and `[drawing]`. Standard ODF 1.4 native fixtures exercise schema,
  PDF/UA validation, fidelity and evidence with independent missing-alternative controls.
- **Explicit text semantics.** Reviewed heading levels and leading table header columns
  are configurable. Targets are preflighted before editing; repeated table declarations
  are split only when that preserves data and identities. Crossing spans and unsafe repeat
  splits fail without publication. Writer exports corrected heading roles. Its current
  header-column export omits PDF `TH`; strict PDF gates continue to reject that omission,
  even when veraPDF reports compliance.

- **Formula, Chart, Image and Base source semantics.** Supplied alternatives and object
  descriptions preserve mathematical expressions, chart data, images, SQL, bindings and
  opaque storage. Normative MathML 3 schemas are bundled under the W3C license. Optional
  native metadata parts can be created explicitly. Math tagging failures remain visible;
  Chart, Image and Base have no PDF export contract, and required production stages fail.
- **Batch workflows.** Strict manifests run independent items with atomic evidence and
  aggregate status. Failures continue; graceful interruption retains completed bundles
  and marks pending work. Forced termination leaves an incomplete running summary.
- **SARIF 2.1.0.** Audit and comparison reports expose registered rules and logical
  locations through explicit, confined source identities. Arbitrary source diagnostics
  and metadata are excluded to protect privacy; see [SARIF](docs/SARIF.md).

### Fixed

- **Installer paths.** The pinned veraPDF installer handles XML-significant characters in
  its destination path.
- **PDF graphical content.** Described illustration-only PDFs no longer fail solely for
  having no extracted text. The content gate reconciles Figure references with executed
  graphical operations on their actual pages; empty, orphan and artifact-only declarations
  remain failures. This is structural content evidence, not proof of pixel visibility.
- **Namespace integrity.** XML fingerprints preserve inherited bindings used by formula
  and other attribute values while ignoring harmless metadata namespace additions.
- **Preservation and reviewed targets.** Table fingerprints cover complete logical data;
  graphic fingerprints include position and payload bytes while remaining stable across
  header-wrapper edits. Spreadsheet postconditions protect formulas, values, references,
  repeats and geometry. Opaque package resources and flat binary data cannot change during
  source remediation. Malformed or non-leading table header bands produce `TXT022`.

### Internal

- **Uniform authored-code gates.** Nested and hidden source files reach lint and type
  checks. Size, complexity and argument limits have no historical exemptions. Central
  lint exceptions must select exact current rules, carry reasons, match authored scopes
  and suppress real diagnostics; unused and overlapping masks, inline suppressions and
  hidden analyzer configuration are rejected. See [Development](docs/DEVELOPING.md).
- **Version authority.** `pyproject.toml` declares the app version. Installed reporting and
  release validation derive from it, with isolated wheel checks.
- **Gate efficiency.** PR checks no longer duplicate branch-push checks; main, version-tag
  and manual runs remain authoritative. Integration uses two isolated workers with crash
  restarts disabled; unit coverage remains sequential. Coverage append and all generated
  property cases are retained. Cached Go tools are isolated from release builds.

## [0.4.0] - 2026-10-07

### Breaking

- **LibreOffice runtime.** PDF export and exporter self-tests require LibreOffice 26.8 or
  newer. Older or unidentifiable installations are rejected. Install a supported runtime;
  no compatibility mode or migration shim is provided.
- **Finding locations.** JSON reports are format 3. A finding's `location` is no longer a
  string naming storage (`content.xml paragraph 3`, `document paragraph 3`) but an object
  `{"path", "member"}` or `null`. `path` is logical and identical for equivalent `.odt` and
  `.fodt` sources (`content/paragraph[3]`, `content/heading[2]`, `content/table[Data]`,
  `meta/title`); `member` carries the package member only for package-level findings such as
  `ODF004` (`manifest`, `META-INF/manifest.xml`). Paragraph indexes no longer count headings,
  heading text moved into the finding's `details.text`, and a finding about a source that
  cannot be opened (`PKG000`, `PDF000`) has no location. `TXT050` is one finding at `styles`
  instead of a list of members, and `ODF900` messages name the part, not the member. The
  Python API takes `Location` in `Report.add`. The grammar is in
  [Rules](docs/RULES.md#locations).

### Added

- **Spreadsheet family.** Spreadsheets (`.ods`, `.ots`, flat `.fods`) now have their own
  semantic audit and plan, as the second implementation of the adapter contract. New rules
  `SHEET001`–`SHEET008` report a sheet without a name or with a default name (`Sheet1`), a
  data-like sheet with no header rows or with merged cells, a picture, chart or object without
  a title or description, hyperlink text that is a raw address, empty sheets after the last
  sheet with content, and hidden sheets, rows or columns. Two operations are configured in a
  new `[spreadsheet]` table: `spreadsheet.sheet_names` renames sheets from an explicit
  mapping, and `spreadsheet.alt_text` sets the title and description of frames, with
  fingerprints as in `[text.alt_text]`. `odfa11y template` lists both, and the review
  checklist has spreadsheet items. See [Rules](docs/RULES.md) and
  [Configuration](docs/CONFIGURATION.md#renaming-sheets).
- **Conservative sheet renaming.** A rename fails, and nothing is written, for an
  unknown sheet, an invalid or colliding new name, a chained or swapped rename, any sheet that
  a formula, range or link refers to by name, and every sheet of a document that embeds
  charts or scripts, or uses dynamic reference functions (`INDIRECT`, `ADDRESS`, `HYPERLINK`).
  Reference matching includes case variants and URL-escaped names. References are not rewritten; table view
  settings and the active-sheet selection follow the renamed sheet.
- **Spreadsheet PDF export.** The pipeline exports spreadsheets with LibreOffice's
  `calc_pdf_Export` filter and runs the PDF audit, veraPDF and the fidelity comparison on
  them. LibreOffice 26.8 table exports can fail `PDF015` and veraPDF 7.2-43. Earlier
  failed gates skip downstream validation;
  [Accessibility](docs/ACCESSIBILITY.md#spreadsheet-pdf-exports) records the tested limits.
- **Marked-content reconciliation in the built-in PDF audit.** Each page's content stream is
  scanned and compared with the structure tree. New rules: `PDF020` (error, an MCID that no
  structure element refers to), `PDF021` (warning, a reference to an MCID its page does not
  contain), `PDF022` (warning, an MCID referred to more than once) and `PDF023` (error, text
  shown outside tagged content and `/Artifact`). Content of form XObjects is not scanned.
  Filtered inline images and unsupported inline color spaces produce `PDF000`; raw image
  samples are skipped by their dimensions. Decoded page content above 64 MiB per document is refused as `PDF000`, like the other input limits.
  Reports of tagged PDFs may now contain these findings; the audit is still not PDF/UA
  validation.
- `odfa11y doctor` now exports a synthetic one-hyperlink document with the installed
  LibreOffice and reports `pdfua_link_descriptions: supported` or `unsupported` (also in
  `--format json`). The self-test requires an explicitly named link to retain its PDF/UA-1
  description. Writer links require a meaningful Name (`office:name`); see
  [link descriptions](docs/ACCESSIBILITY.md#link-descriptions).
  `PDF019` remains an error. `doctor` accepts `--soffice` and `--timeout`, and now exits `3`
  when LibreOffice is missing or its export fails, after printing the versions it found.
  Text pipeline exports record the same capability under `toolchain.LibreOffice` in
  `run.json`, using one isolated self-test export per run. Probe files are not bundled.

### Changed

- Documents of a spreadsheet kind are no longer served by the generic adapter: `audit`
  reports `adapter: spreadsheet` and no longer emits `ODF009` for them, `SHEET` findings can
  now fail an audit or `--strict` run, and the pipeline's PDF stages run instead of being
  `not-applicable`. Renaming a sheet changes the name Calc's default page
  header prints, which the fidelity stage reports as `FID003`.

### Fixed

- PDF audit enforces the file-size limit before constructing the PDF parser, so an
  oversized input is rejected before parsing starts. The size threshold is unchanged.
- The text-preservation check no longer counts the image bytes that a flat XML document embeds
  (`office:binary-data`) as visible text, so a flat and a packaged copy of one document
  compare equal.

### Internal

- A regression corpus of fourteen small documents authored by LibreOffice Writer 24.2
  (`tests/corpus`, nineteen files including flat-XML twins) is audited for its exact rule
  ids, hashed, checked for package/flat equivalence and schema validity, and remediated
  idempotently; an integration test runs the pipeline on three of them with real LibreOffice.
  The sdist ships the corpus with the tests.

## [0.3.0] - 2026-10-07

This release makes the ODF core independent of any document family: ODFA11y now recognises
every kind of OpenDocument file, packaged or flat, and the text-document logic became the
first *family* plug-in. It is a deliberate break from 0.2.0 with no compatibility layer; the
configuration file, the report and evidence formats, the rule identifiers and the Python API
all changed. Review the **Breaking** list before upgrading.

### Breaking

- **Python API.** `OdtDocument` is `OdfDocument` and `OdtPackage` is `PackageStorage` (a ZIP
  package; `FlatXmlStorage` is its flat-XML sibling), `audit_odt` is `audit_odf`, and
  `ODT_MIMETYPE` is gone. A document is read through logical parts
  (`document.tree(Part.CONTENT)`), never member names. Everything specific to text moved to
  `odfa11y.families.text`: the operations `LinkifyAddresses`, `RemoveEmptySpacers`,
  `NormalizeSpacing`, `SetAltText`, `MarkHeaderRows`, their `AltText` and `HeaderRows`
  parameters, and the text helpers formerly in `odfa11y.odf`. `Operation`, `Outcome` and
  `Status` are in `odfa11y.adapter`; `odfa11y.remediation` keeps `remediate`, `SetMetadata`,
  `SetOdfVersion` and `RemediationResult`. `export_pdfua` takes an `ExportSettings` (including
  the family's PDF filter), `write_bundle` takes a `Redactor`, `PipelineOptions` selects a
  `profile` instead of `verapdf`/`strict`, and `SchemaResult.violations` holds `Violation`
  objects.
- **Configuration.** Family decisions moved under the family's table: `[remediation]`,
  `[table_headers]`, `[alt_text]` and `[spacing]` are now `[text.remediation]`,
  `[text.table_headers]`, `[text.alt_text]` and `[text.spacing]`. A header entry may also be
  `{ rows = N, fingerprint = "…" }`. `[document]` and `[fidelity]` are unchanged. A table for
  another family, or for a family the document does not belong to, is an error.
- **Rule identifiers.** Text rules are renamed `TXT…`: `SEM001`–`SEM005` → `TXT001`–`TXT005`,
  `IMG001` → `TXT010`, `TBL001`/`TBL002` → `TXT020`/`TXT021`, `LNK001` → `TXT030`, `LAY001` →
  `TXT040`, `STYLE001` → `TXT050`. `PKG001` (no declared media type) and `PKG002` (an optional
  package member is missing) are now warnings with new meanings; `ODF004` compares the
  manifest with the document's own media type. Remedies are the new config keys
  (`text.alt_text`, …).
- **Reports.** JSON reports are format 2: `kind` is `odf`, locations name the stored member
  (`content.xml`, or `document` for flat XML), and `metadata` carries `document_kind`,
  `media_type`, `layout`, `family` and `adapter`.
- **Command line.** `pipeline` selects `--profile {inspect,verify,production}` (default
  `verify`) and no longer takes `--verapdf` or `--strict`; `production` is the old
  `--verapdf --strict`. `template` refuses a document it cannot read instead of printing an
  empty plan, and `styles` is available only for families that define it.
- **Evidence.** `run.json` is format 2 (`document` replaces `input`, plus `plan_sha256`,
  `profile`, `fonts`, `libraries`, `environment`, `human_review`; stage `identify-source` and
  status `not-applicable` are new). The remediated file keeps the source's extension
  (`remediated.fodt`, not always `remediated.odt`). `check-evidence` treats the manifest as
  untrusted and reports symbolic links and nested files it used to ignore.
- **Generated styles.** `NormalizeSpacing` names its styles `A11ySpacing_<style>_<digest>`.
  A style named that way is reused only when it is provably ODFA11y's own derivation; one made
  by version 0.2 has no digest, so re-applying a plan to a 0.2 output is not recognised (apply
  the plan to the original instead).

### Added

- **ODF family core.** Every OpenDocument kind is recognised from its declared media type,
  packaged or as flat XML (`.fodt`, …): text, spreadsheet, presentation, graphics, formula,
  chart, image and database, with templates, master and web documents and the deprecated and
  legacy media types. New findings report an unrecognised media type (`ODF005`), a body that
  contradicts it (`ODF006`), a misleading extension (`ODF007`), deprecated or legacy kinds
  (`ODF008`), a family without semantic audit (`ODF009`) and a flat root that is not
  `office:document` (`ODF010`) or a package's content root that is not
  `office:document-content` (`ODF011`). Packages need only a manifest and content: a missing
  `mimetype`, `styles.xml` or `meta.xml` is a warning, not a rejection.
- **Document families.** The text family is the first implementation of the adapter contract;
  other families are served by the generic adapter (common checks, common `[document]`
  decisions, an honest `ODF009`) until they get their own. A plan for another family's
  operations is refused, as is remediation of an unrecognised document.
- **Assurance profiles** for `pipeline`, recorded with their effective gates, and stages that
  are `not-applicable` rather than skipped when a family has no PDF export; `production`
  fails such a document because it requires PDF validation.
- **Plan fingerprints.** `template` prints a fingerprint for each graphic and table it
  suggests; an entry carrying one fails when the object it addresses has drifted.
- **PDF link correspondence.** Each link annotation must be referenced by a Link element on its
  page (`PDF016`); `PDF017` reports a Link element that refers to no annotation and `PDF018` an
  annotation referenced from another page; `PDF019` reports a link with neither `/Contents`
  nor a Link element `/Alt` (newer LibreOffice releases omit the description that older ones
  derive from the link text).
- **Resource limits.** Tool output is captured only up to a size limit and a timed-out tool's
  process tree is killed; PDFs above 256 MiB, 5,000 pages or 500,000 structure elements are
  refused; flat XML is limited to 256 MiB.
- Evidence records the document's kind, layout and adapter, the fonts of both PDFs and the
  libraries and locale of the run.

### Fixed

- `check-evidence` followed absolute manifest names, `..` components and symbolic links out
  of the bundle, and ignored every file named `manifest.json` wherever it lay.
- Evidence leaked local paths: a failed LibreOffice run recorded its whole command line, and
  even a successful run wrote the temporary working directory into the raw veraPDF report. All
  textual evidence now passes through a redactor and failures record bounded, path-free
  diagnostics.
- The schema regression gate compared violation messages only, so a violation fixed in one
  place hid an identical one introduced elsewhere. Violations are now identified by their
  failing element.
- The built-in PDF check passed a document when any one Link element existed, however many
  link annotations lacked one.
- `NormalizeSpacing` could reuse or reinterpret an author's style that happened to have its
  generated name, and removed same-named styles; it now fails without touching them.
- Two alt-text selectors addressing one graphic silently overwrote each other; selectors are
  now resolved before any edit and conflicting assignments fail.
- `template` reported success for an unreadable or nonexistent document; it now refuses.
- `pipeline` could fail before publishing evidence when the source could not be read; it now
  publishes a bundle naming the failed stage.
- Setting the language created `office:styles` after the body in documents without one,
  which the schema gate rejected; setting metadata on a flat document without `office:meta`
  did the same. A package without `meta.xml` is refused with a clear message.
- Text rules matched headers and footers of flat documents (which a package keeps in
  `styles.xml`), so the same document audited and edited differently by layout. Text queries
  are now scoped to the document body.
- Flat documents lost their comments, processing instructions and a DOCTYPE when edited.
- `remediate` rewrote documents the audit refuses: an unrecognised media type, or a manifest
  or body that contradicts the mimetype. It now refuses them. Blank titles and descriptions
  are refused instead of written empty; `en_US`-style language tags are normalised to BCP 47
  and private-use tags are accepted.
- `check-evidence` crashed on a manifest name that is not valid text and echoed 5,000-character
  names; names that other filesystems cannot hold (Windows device names, trailing dots, `:`),
  names that differ from `manifest.json` only in case, and artifacts named `run.json` or
  `REVIEW.md` are now rejected.
- A damaged `mimetype` member (stray whitespace, non-ASCII bytes) ended the audit as an
  unrecognised type; it is now a `PKG001` warning and detection continues from the manifest.
- On Windows, `soffice --version` never returns; LibreOffice is identified by its file
  version there.

### Internal

- Package boundaries (`odf` core, `adapter` contract, `families.<family>`, registry) enforced
  by tach with families as nested modules, plus a quality gate that fails when core code names
  a family's XML elements. A test registers a stand-in family through the registry alone.
- Synthetic documents of every kind, as packages and flat XML, are tested for detection,
  audit, schema validity and cross-family rejection.

## [0.2.0] - 2026-10-07

This release is a deliberate break from 0.1.0 with no compatibility layer: the Python
API, command line, configuration file and report format all changed. Review the
**Breaking** list before upgrading.

### Breaking

- **Python API.** The flat modules became packages (`odfa11y.audit`, `odfa11y.remediation`,
  `odfa11y.pdf`, `odfa11y.report`, `odfa11y.odf`, `odfa11y.fidelity`, `odfa11y.evidence`,
  `odfa11y.config`, `odfa11y.pipeline`, `odfa11y.cli`); each package's API is exactly what
  its `__init__` exports and `import odfa11y` exposes only `__version__`. `remediate_odt`,
  `RemediationOptions`, `normalize_paragraph_spacing`, `load_remediation_config`,
  `AuditReport`, `Issue` and `run_verapdf` are replaced by `remediate` with typed operations,
  `load_config`, `Report`, `Finding` and `validate_pdfua`. Expected failures are now
  `odfa11y.errors` exceptions instead of `ValueError`, `RuntimeError` and `KeyError`.
- **Command line.** `verify`, `verify-pdf`, `normalize-spacing` and `export-pdfua` are gone
  (use `audit`, `remediate` with `[spacing]`, and `export`). Every remediation flag
  (`--title`, `--language`, `--linkify`, `--table-header`, `--alt-map`, `--target-version`, …)
  and `--schema PATH`/`--manifest-schema PATH` were removed: decisions live in one TOML
  file. `pipeline` now takes `--config` and `--output-dir` and publishes an evidence
  directory instead of writing loose files.
- **Configuration.** `document.target_version` is now `document.odf_version`, and omitting
  it keeps the declared version; 0.1.0 silently relabelled every document as 1.4. New
  `[spacing]` and `[fidelity]` tables.
- **Selectors fail closed.** A table name, graphic key or spacing reference that matches
  nothing now fails the run (0.1.0 skipped it silently), as does a header-row count that
  conflicts with existing header rows. `remediate` refuses a destination that is the source.
- **Report format.** JSON reports are `{"format": 1, "kind", …, "findings"}`: `issues`
  became `findings`, the boolean `fixable` became `remedy` (the configuration key that
  holds the decision), and `audit` of several files returns an array. `ODF900`/`ODF901`
  merged into one warning `ODF900`; `ODF001`–`ODF003` now flag *inconsistent* version
  declarations instead of "not 1.4".
- **veraPDF selection.** `--verapdf` is now a plain switch (it no longer consumes the next
  argument); `--verapdf-path PATH` names the executable and implies `--verapdf`.
- **Installation.** The `dev` extra was replaced by a `dev` dependency group, and
  `pillow` and `pypdfium2` are new runtime dependencies.

### Added

- Official OASIS ODF 1.3 and 1.4 schemas ship unmodified (digests recorded and verified);
  `audit --schema` validates against the declared version, and `remediate` refuses any
  result with a schema violation the source did not already have.
- One executor for typed, idempotent operations (`applied`/`unchanged`/`failed` per
  target), `remediate --dry-run`, atomic publication, text-preservation guard, and
  `odfa11y template` to print a commented configuration for the open decisions.
- `compare`: page, text, link and rendered-ink fidelity between two ODTs or PDFs with a
  configurable policy and diff images; see [Fidelity](docs/FIDELITY.md).
- `pipeline --output-dir`: a hashed evidence directory with run record, review sheet,
  artifacts and raw veraPDF report, and `check-evidence` to verify it;
  see [Evidence](docs/EVIDENCE.md).
- veraPDF failures are parsed into one finding per failed rule with clause, test number and
  sample contexts, and the validator's version is recorded.
- PDF structure checks for skipped or too-deep headings (`PDF012`), malformed lists
  (`PDF013`) and tables (`PDF014`), tables without header cells (`PDF015`) and link
  annotations without Link structure elements (`PDF016`), validated against real
  LibreOffice exports and veraPDF.
- `PKG007` for unsafe ZIP member names, which the writer now also refuses.
- A rule registry with severity, category and remedy, checked against `docs/RULES.md`.
- Packaging and licensing: the license expression is `MPL-2.0 AND LicenseRef-OASIS-ODF-Notice`;
  the verbatim OASIS notices ship as `odf/schemas/NOTICE.txt` in the wheel (inside the package
  and under `dist-info/licenses`) and the source archive. Release verification now rejects a
  wheel or source archive whose notice or `LICENSE` differs from the repository, or a wheel
  whose package files differ from `src/odfa11y`.
- Releases are started by a manual run of the Checks workflow on `main` (`gh workflow run checks.yml --ref main -f release=true`) instead of by pushing a tag: after the gate passes it creates a draft release targeting the tested commit, and publishing the draft creates the tag.
- Release assets include `SHA256SUMS` and a build-provenance attestation; CI rebuilds the
  distributions and requires identical bytes. A weekly dependency-advisory workflow, issue
  and pull-request templates (warning against uploading real documents).
- `py.typed`; the CI `CI gate` job and a ruleset file requiring only it.

### Fixed

- Hostile or unusual inputs: malformed `settings.xml`, encrypted ZIP members and non-executable
  tool paths now produce domain errors (and a published evidence bundle) instead of crashes;
  pdfium rendering errors are reported as tool failures.
- Linkification only touches plain prose (never existing links, annotations or alternative
  text), and spacer removal never removes paragraphs that carry markers or frames;
  the audit and the remediation share one definition of each.
- Outputs respect the umask instead of being created owner-only, and `REVIEW.md` escapes
  table cells.
- Alternative text was inserted before the image, which the ODF schema rejects; it is now
  placed where the schema allows.
- Corrupt ZIP members could escape as `zlib.error`, `EOFError` or an operating-system
  `OSError` (found by property tests, including on Windows) instead of an invalid-package
  error.
- Remediation re-serialized every XML member even when unchanged; only edited members are
  now rewritten and all others stay byte-identical.
- The synthetic test documents were not valid ODF; they are now schema-valid.

### Internal

- Package boundaries enforced by tach; ty type checking with `types-lxml`; Hypothesis
  properties (including idempotence and schema validity of operation subsets); a coverage
  floor; CI split into static, per-OS quality and integration jobs with real LibreOffice
  and a checksum-pinned veraPDF, plus Dependabot.

## [0.1.0] - 2026-10-06

- First release.
