# ODFA11y

Audit and explicitly remediate LibreOffice Writer documents, export them as PDF/UA-1,
and keep evidence of what changed and what a person must still check.

ODFA11y works on both the editable `.odt` source and the exported PDF, because an
accessible source does not guarantee an accessible export. It audits package structure,
metadata, headings, graphics, tables and links; applies the changes *you* decide in one
TOML file, refusing anything that alters the text or breaks the ODF schema; exports with
LibreOffice; inspects the PDF and runs veraPDF; compares the source and candidate renders;
and publishes a hashed evidence directory. It is conservative by design: it never invents
alternative text, heading levels or table headers, and a clean report is not an
accessibility certificate. Reading order, alt-text quality and the visual result still
need a person.

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
  --output-dir evidence --verapdf --strict
uv run --no-sync odfa11y check-evidence evidence
```

`evidence/` then holds the remediated ODT and PDF, the veraPDF report, a run record and a
`REVIEW.md` that separates machine-established facts from the human review still required.

## Commands

| Command | Purpose |
| --- | --- |
| `audit FILE...` | Read-only checks of ODT or PDF files; `--schema` validates ODT against the ODF schema, `--verapdf` validates PDFs. |
| `template FILE` | Print a commented configuration for the decisions an audit leaves open. |
| `remediate SRC DEST --config FILE` | Apply the configured operations; `--dry-run` shows outcomes without writing. |
| `export SRC DEST` | Export an ODT to PDF/UA with LibreOffice. |
| `compare A B` | Compare two ODTs or PDFs for pages, text, links and rendered ink. |
| `pipeline SRC --config FILE --output-dir DIR` | Remediate, export, validate, compare and keep evidence. |
| `styles FILE` | Paragraph-style usage and effective spacing. |
| `check-evidence DIR` | Verify an evidence directory against its manifest. |
| `doctor` | Dependency and external-tool versions. |

Use `uv run --no-sync odfa11y COMMAND --help` for options. The staged
[workflow](docs/WORKFLOW.md) is for human review between steps.

## Library use

Each package exposes its API through its `__init__`: for example
`odfa11y.audit.audit_odt`, `odfa11y.remediation.remediate` with the operation classes,
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
- [Releasing](docs/RELEASING.md): version tags, draft assets and the required CI check.
- [Changelog](CHANGELOG.md): release outcomes.

## License

Created and maintained by Ervins Strauhmanis. The project is licensed under the [Mozilla Public License 2.0](LICENSE)
(`MPL-2.0`). Dependencies and external applications retain their own licenses.
