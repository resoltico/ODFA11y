# ODFA11y

Audit OpenDocument sources, record human decisions, apply guarded changes and check
native PDF/UA-1 exports. ODFA11y supports text, spreadsheet, presentation, drawing,
formula, chart, image and database source audits. Export support and measured limits
are described in [Accessibility](docs/ACCESSIBILITY.md).

## Start here

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and restore the
source checkout's locked environment:

```sh
uv sync --locked
uv run --no-sync odfa11y audit original.odt --schema
uv run --no-sync odfa11y plan original.odt > reviewed.toml
# Uncomment only reviewed answer fields; unanswered tables are inert.
uv run --no-sync odfa11y remediate original.odt reviewed.odt --plan reviewed.toml --dry-run
uv run --no-sync odfa11y run original.odt --plan reviewed.toml \
  --output-dir evidence --profile pdf
uv run --no-sync odfa11y verify-evidence evidence
```

Python 3.15 or newer is required; [.python-version](.python-version) selects the development
interpreter. Source audits need no office application. Native work needs
LibreOffice 26.8 or newer; PDF validation needs [veraPDF](https://verapdf.org/) and Java.
Run `uv run --no-sync odfa11y doctor` to identify tools and measure exporter capabilities.

Plans bind to the exact reviewed source. Remediation preserves protected content and
publishes candidates passing preservation/schema guards to a separate destination. A successful dry run writes
no destination. Production runs reject warnings and require veraPDF; review the retained
`REVIEW.md` and actual publication before distribution. Machine checks do not certify accessibility.

## Compare responsibilities

| Responsibility | ODFA11y | Native application / independent review |
| --- | --- | --- |
| Inspect ODF source | Read-only semantic, package and optional schema checks across eight families. | Review authored meaning, layout and unsupported structures in the editor. |
| Repair source | Apply supplied decisions to a separate candidate through preservation/schema guards. | Choose truthful descriptions, intended structure and navigation. |
| Export PDF | Invoke supported LibreOffice filters with private captures/profiles. | LibreOffice determines actual font, tagging and layout output. |
| Validate PDF/UA | Built-in smoke checks plus requested/required veraPDF validation. | veraPDF checks machine-verifiable conformance; people assess usability. |
| Compare and retain evidence | Compare text, URI targets and optional rendered ink; publish verifiable bundles. | Inspect actual differences, reading order and remaining review items. |

These responsibilities complement one another. A passing source audit, validator or evidence
hash does not establish an accessible publication on its own.

## Choose a task

- [Worked example](docs/WALKTHROUGH.md): a real plan and remaining-finding prediction.
- [Workflow](docs/WORKFLOW.md): audit, review, remediate, export and compare.
- [Plans](docs/PLAN.md): source binding, fingerprints and generated answer reference.
- [Commands and exit statuses](docs/CLI.md): generated options for every CLI command.
- [Application API](docs/API.md): root use cases, typed results, `Tools` and `Profile`.
- [Batch](docs/BATCH.md): independent document runs and aggregate outcomes.
- [Evidence](docs/EVIDENCE.md), [JSON Schemas](docs/SCHEMAS.md) and [SARIF](docs/SARIF.md): consume and verify results.
- [Fidelity](docs/FIDELITY.md): text, URI and rendered-ink comparison policy.
- [Accessibility](docs/ACCESSIBILITY.md) and [native capability probes](docs/CAPABILITIES.md): source, native, PDF and human boundaries.
- [Development](docs/DEVELOPING.md), [architecture](docs/ARCHITECTURE.md) and [releases](docs/RELEASING.md): contribute and qualify artifacts.
- [Rules](docs/RULES.md) and [changelog](CHANGELOG.md).

## License

Created and maintained by Ervins Strauhmanis. Project code uses [AGPL-3.0-only](LICENSE).
See the [project notice](PROJECT-NOTICE.md) for scope and source availability,
[commercial licensing status](LICENSE-COMMERCIAL.md) for the scope of separate terms, and
[contribution terms](.github/CONTRIBUTING.md) before submitting changes.
Bundled unmodified OASIS schemas retain their [OASIS notice](src/odfa11y/odf/schemas/NOTICE.txt);
MathML retains its [W3C notice](src/odfa11y/odf/schemas/mathml/NOTICE.txt), and formula
classifications their [OASIS notice](src/odfa11y/odf/formula_data/NOTICE.txt).
[Schema provenance](src/odfa11y/odf/schemas/PROVENANCE.toml) records sources and digests.
Dependencies and external applications retain their licenses. ODFA11y is not affiliated
with OASIS, LibreOffice or veraPDF and does not redistribute those applications.
