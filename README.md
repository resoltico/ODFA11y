# ODFA11y

Audit and explicitly remediate LibreOffice Writer documents, export them as
PDF/UA-1, and inspect the resulting PDF.

ODFA11y works on both the editable `.odt` source and the exported PDF. It checks
ODF package structure, metadata, headings, graphics, tables and links; applies
operator-selected fixes; and produces text or JSON reports. PDF diagnostics use
pypdf. Optional veraPDF validation checks machine-verifiable PDF/UA-1 requirements.
A clean report does not prove that a document is accessible: reading order,
alternative-text quality and the visual result still need human review.

## Start here

From the source directory, install [uv](https://docs.astral.sh/uv/getting-started/installation/)
and restore the locked environment:

```bash
uv sync --locked
uv run --no-sync odfa11y audit original.odt
```

Python 3.14 is the baseline. uv uses the development interpreter specified in
[.python-version](.python-version); the supported range and dependencies live in
[pyproject.toml](pyproject.toml). Commands shown here use a POSIX shell.

Create `document.toml` using the example in the
[configuration guide](docs/CONFIGURATION.md#example), replace its sample values,
then write to a separate output file:

```bash
uv run --no-sync odfa11y remediate original.odt reviewed.odt --config document.toml
uv run --no-sync odfa11y audit reviewed.odt --strict
```

Inspect the remediated document in Writer before exporting. With LibreOffice
installed and `soffice` or `libreoffice` on `PATH`:

```bash
uv run --no-sync odfa11y export-pdfua reviewed.odt reviewed.pdf
uv run --no-sync odfa11y verify-pdf reviewed.pdf --strict
```

If veraPDF and its Java runtime are installed, add `--verapdf` to `verify-pdf`.
Both inspection and validation remain necessary; neither replaces human review.

## Choose a command

| Command | Purpose |
| --- | --- |
| `audit` | Read-only ODT package, metadata and semantic checks; optional ODF schemas. |
| `remediate` | Apply explicit metadata and structural choices to an ODT. |
| `styles` | Inspect paragraph-style usage and effective spacing. |
| `normalize-spacing` | Copy reference spacing to selected paragraph styles. |
| `export-pdfua` | Export an ODT through LibreOffice's Writer PDF/UA filter. |
| `verify-pdf` | Inspect a PDF and optionally invoke veraPDF. |
| `verify` | Audit an ODT and optionally its PDF counterpart. |
| `pipeline` | Combine remediation, audit, export and PDF inspection. |
| `doctor` | Report dependency versions and external-tool availability. |

Use `uv run --no-sync odfa11y COMMAND --help` for the complete option list.
`pipeline` stops before export when its ODT audit has errors, or warnings with
`--strict`. Use the staged [workflow](docs/WORKFLOW.md) for human review between steps.

## Documentation

- [Workflow](docs/WORKFLOW.md): staged commands, reports, exit codes and troubleshooting.
- [Configuration](docs/CONFIGURATION.md): the maintained TOML example and CLI overrides.
- [Accessibility and limits](docs/ACCESSIBILITY.md): scope, known limitations and human checks.
- [Rule reference](docs/RULES.md): stable finding identifiers and their meanings.
- [Development](docs/DEVELOPING.md): setup, checks, CI and packaging.
- [Architecture](docs/ARCHITECTURE.md): implementation responsibilities and invariants.
- [Releasing](docs/RELEASING.md): initial publication, version tags and draft package assets.
- [Changelog](CHANGELOG.md): release outcomes after the initial public release.

## License

Created and maintained by Ervins Strauhmanis. The project is licensed under the [Mozilla Public License 2.0](LICENSE)
(`MPL-2.0`). Dependencies and external applications retain their own licenses.
