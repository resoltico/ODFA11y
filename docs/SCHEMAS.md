# JSON Schemas

Draft 2020-12 schemas ship in `odfa11y/schemas`.
Registered facts and decisions are closed vocabularies.

| Interface | Schema version | Schema |
| --- | --- | --- |
| `audit` | 1 | [audit.schema.json](../src/odfa11y/schemas/audit.schema.json) |
| `plan` | 1 | [plan.schema.json](../src/odfa11y/schemas/plan.schema.json) |
| `remediation` | 1 | [remediation.schema.json](../src/odfa11y/schemas/remediation.schema.json) |
| `export` | 1 | [export.schema.json](../src/odfa11y/schemas/export.schema.json) |
| `comparison` | 1 | [comparison.schema.json](../src/odfa11y/schemas/comparison.schema.json) |
| `run` | 1 | [run.schema.json](../src/odfa11y/schemas/run.schema.json) |
| `batch` | 1 | [batch.schema.json](../src/odfa11y/schemas/batch.schema.json) |
| `evidence-verification` | 1 | [evidence-verification.schema.json](../src/odfa11y/schemas/evidence-verification.schema.json) |
| `doctor` | 1 | [doctor.schema.json](../src/odfa11y/schemas/doctor.schema.json) |
| `report` | 1 | [report.schema.json](../src/odfa11y/schemas/report.schema.json) |
| `plan-file` | 1 | [plan-file.schema.json](../src/odfa11y/schemas/plan-file.schema.json) |

CLI JSON is the corresponding application result record, including its schema version.
The `audit` result always contains an `inputs` array; each input retains its reports.
The `comparison` result contains its report, strict flag and effective exit status.
The `plan` result contains the source report and optional unanswered TOML template.
The `plan-file` schema describes parsed TOML; its header owns `schema_version`.
See [application API](API.md) and [evidence](EVIDENCE.md).
