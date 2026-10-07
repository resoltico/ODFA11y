# Changelog

Notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
