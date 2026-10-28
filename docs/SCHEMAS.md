# JSON Schemas

Draft 2020-12 schemas ship in `odfa11y/schemas`.
Registered facts and decisions are closed vocabularies.

| Interface | Format | Schema |
| --- | --- | --- |
| `report` | 6 | [report.schema.json](../src/odfa11y/schemas/report.schema.json) |
| `audit` | 1 | [audit.schema.json](../src/odfa11y/schemas/audit.schema.json) |
| `run` | 3 | [run.schema.json](../src/odfa11y/schemas/run.schema.json) |
| `batch` | 2 | [batch.schema.json](../src/odfa11y/schemas/batch.schema.json) |
| `doctor` | 1 | [doctor.schema.json](../src/odfa11y/schemas/doctor.schema.json) |
| `remediation` | 1 | [remediation.schema.json](../src/odfa11y/schemas/remediation.schema.json) |
| `plan` | 1 | [plan.schema.json](../src/odfa11y/schemas/plan.schema.json) |

CLI audit/comparison JSON contains report objects (or an array of them).
The `audit` schema describes the root application's per-input result record.
The `plan` schema describes the parsed TOML structure; its header owns `format`.
See [application API](API.md) and [evidence](EVIDENCE.md).
