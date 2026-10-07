# ODFA11y

Recognise and check every kind of OpenDocument file, and audit, explicitly remediate and
export text documents as PDF/UA-1 with evidence of what changed and what a person must still
check.

ODFA11y works on both the editable ODF source and the exported PDF, because an accessible
source does not guarantee an accessible export.

- **Every OpenDocument kind, packaged or flat XML:** recognised from its declared media type
  and given the common checks of package structure, document kind, version, metadata and
  schema validity.
- **Text documents (`.odt`, templates, master and web documents) only:** semantic audit of
  headings, graphics, tables and links; remediation of the changes *you* decide in one TOML
  file, refusing anything that alters the text or breaks the ODF schema; LibreOffice export;
  PDF inspection and veraPDF; comparison of source and candidate renders; and a hashed
  evidence directory.
- **Other families (spreadsheets, presentations, drawings and the rest):** recognised and
  checked in common only. The audit reports `ODF009` rather than implying semantic coverage;
  see [Accessibility and limits](docs/ACCESSIBILITY.md#document-families).

It is conservative by design: it never invents alternative text, heading levels or table
headers, and a clean report is not an accessibility certificate. Reading order, alt-text
quality and the visual result still need a person.

## Start here

From the source directory, install [uv](https://docs.astral.sh/uv/getting-started/installation/)
and restore the locked environment:

```bash
uv sync --locked
uv run --no-sync odfa11y audit original.odt
```

Python 3.14 is the baseline; [.python-version](.python-version) selects the development
interpreter and [pyproject.toml](pyproject.toml) holds the supported range and
dependencies. Commands use a POSIX shell. External applications are optional:
[LibreOffice](https://www.libreoffice.org/) for export and comparison, and
[veraPDF](https://verapdf.org/) with its Java runtime for PDF/UA validation.

The shortest complete path:

```bash
uv run --no-sync odfa11y template original.odt > document.toml   # list open decisions
# edit document.toml: uncomment and complete only the decisions you have made
uv run --no-sync odfa11y pipeline original.odt --config document.toml \
  --output-dir evidence --profile production
uv run --no-sync odfa11y check-evidence evidence
```

`evidence/` then holds the remediated document and PDF, the veraPDF report, a run record and a
`REVIEW.md` that separates machine-established facts from the human review still required.
`--profile` selects how much assurance a run requires: `inspect`, `verify` (the default) or
`production` (veraPDF required, warnings fail).

## Commands

| Command | Purpose |
| --- | --- |
| `audit FILE...` | Read-only checks of ODF or PDF files; `--schema` validates ODF against the ODF schema, `--verapdf` validates PDFs. |
| `template FILE` | Print a commented configuration for the decisions an audit leaves open. |
| `remediate SRC DEST --config FILE` | Apply the configured operations; `--dry-run` shows outcomes without writing. |
| `export SRC DEST` | Export an ODF document to PDF/UA with LibreOffice. |
| `compare A B` | Compare two ODF documents or PDFs for pages, text, links and rendered ink. |
| `pipeline SRC --config FILE --output-dir DIR [--profile P]` | Remediate, export, validate, compare and keep evidence. |
| `styles FILE` | Paragraph-style usage and effective spacing. |
| `check-evidence DIR` | Verify an evidence directory against its manifest. |
| `doctor` | Dependency and external-tool versions, and whether the installed LibreOffice describes hyperlinks in its PDF/UA export (`pdfua_link_descriptions`). |

Use `uv run --no-sync odfa11y COMMAND --help` for options. The staged
[workflow](docs/WORKFLOW.md) is for human review between steps.

## Library use

Each package exposes its API through its `__init__`: for example
`odfa11y.audit.audit_odf`, `odfa11y.remediation.remediate` with the operation classes,
`odfa11y.pdf.export_pdfua` and `odfa11y.pipeline.run_pipeline`. See
[Architecture](docs/ARCHITECTURE.md).

## Documentation

- [Workflow](docs/WORKFLOW.md): staged commands, reports, exit statuses and troubleshooting.
- [Configuration](docs/CONFIGURATION.md): the maintained TOML example and every field.
- [Fidelity](docs/FIDELITY.md): what the render comparison measures and how to set its policy.
- [Evidence](docs/EVIDENCE.md): the evidence directory, its record and verification.
- [Accessibility and limits](docs/ACCESSIBILITY.md): scope, known limitations and human checks.
- [Rule reference](docs/RULES.md): stable finding identifiers and their meanings.
- [Development](docs/DEVELOPING.md): setup, checks, CI and packaging.
- [Architecture](docs/ARCHITECTURE.md): implementation responsibilities and invariants.
- [Releasing](docs/RELEASING.md): starting a release, draft assets and the required CI check.
- [Changelog](CHANGELOG.md): release outcomes.

## Status and roadmap

Current work and planned features are tracked in [GitHub issues](https://github.com/resoltico/ODFA11y/issues)
and [pull requests](https://github.com/resoltico/ODFA11y/pulls).

## License

Created and maintained by Ervins Strauhmanis. The project is licensed under the [Mozilla Public License 2.0](LICENSE)
(`MPL-2.0`). Dependencies and external applications retain their own licenses.

The package also bundles unmodified copies of the OASIS OpenDocument Relax NG schemas, which
are **not** MPL-2.0: they remain © OASIS Open and are distributed under OASIS's own notice,
reproduced verbatim in [src/odfa11y/odf/schemas/NOTICE.txt](src/odfa11y/odf/schemas/NOTICE.txt)
and shipped in every wheel and source archive. ODFA11y is not affiliated with or endorsed by OASIS.
LibreOffice, veraPDF and OpenDocument are names of their respective owners; the project
only invokes the first two as external applications and does not redistribute them.
