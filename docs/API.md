# Application API

Import `odfa11y` for supported use cases. Results own `exit_status`; core work produces no
terminal output. Unusable arguments, inputs, tools and output locations can raise domain
exceptions. [Executable examples](../tools/core_examples.py) are qualified against an
installed wheel outside the checkout, without importing the CLI.

```python
import odfa11y

checks = odfa11y.audit(["original.odt"], schema=True)
questions = odfa11y.plan("original.odt")
# Review questions.template and save the selected answers as reviewed.toml.
result = odfa11y.run(
    "original.odt",
    "reviewed.toml",
    "evidence",
    tools=odfa11y.Tools(),
    profile=odfa11y.profile_named("production"),
)
integrity = odfa11y.verify_evidence("evidence")
```

| Use case | Result |
| --- | --- |
| `audit` | `AuditRun`: per-input reports/failures and combined status. |
| `plan` | `PlanResult`: source report and optional bound disabled-answer template. |
| `remediate` | `RemediationResult`: all outcomes/violations, schema check and publication. |
| `export` | `ExportResult`: published PDF path; validate separately. |
| `compare` | `ComparisonResult`: fidelity report and effective acceptance status. |
| `run`, `run_batch` | `RunRecord` / `BatchRecord`: profiles, stages, capabilities and evidence. |
| `doctor` | `DoctorRecord`: identities, scoped probes and controlled failure status. |
| `verify_evidence` | `VerificationResult`: recorded-file integrity problems. |

`Tools` selects `soffice`, `verapdf` and per-call `timeout`. Use `profile_named`/`PROFILES`
for [assurance profiles](WORKFLOW.md#retain-evidence). Native use cases accept typed progress
observers; callbacks must not raise. See [native limits](ACCESSIBILITY.md#native-execution-limits).

Inspect `AuditRun.reports` and `.failures` separately. `.render` produces report output;
`.as_dict` produces the [per-input record](SCHEMAS.md). SARIF rendering refuses partial logs;
use `preflight_sarif` before expensive work. `Plan.for_source`, `Decision`, registered kinds
and `decode_answer` support programmatic answers; `load_plan` reads reviewed TOML.
Explicit rebind still enforces fingerprints and preservation. Internal packages have no
compatibility aliases and low-level model/native calls leave guard policy to their caller.
