# Application API

Import `odfa11y` for supported library work. Each use case returns a value with
`exit_status`; exceptions report unusable inputs, tools or output locations. Core
operations produce no terminal output and do not import the CLI.

| Use case | Result |
| --- | --- |
| `audit(sources, tools=Tools(), schema=False, validate_pdf=False, strict=False)` | `AuditRun`: independent inputs, completed reports, failures and combined status. |
| `plan(source)` | `PlanResult`: source report and a bound disabled-answer template. |
| `remediate(source, destination, plan, dry_run=False, rebind=False)` | `RemediationResult`: every outcome/violation and physical publication. |
| `export(source, destination, tools=Tools())` | `ExportResult`: published PDF path. |
| `compare(source, candidate, tools=Tools(), plan=None, strict=False)` | `ComparisonResult`: fidelity report and acceptance status. |
| `run(source, plan, output_dir, tools=Tools(), profile=PROFILES["verify"])` | `RunRecord`: stages, effective profile, capabilities and evidence. |
| `run_batch(manifest, output_dir, tools=Tools(), profile=PROFILES["verify"])` | `BatchRecord`: per-item evidence and effective aggregate status. |
| `doctor(tools=Tools())` | `DoctorRecord`: identities, scoped observations, controlled error and status. |
| `verify_evidence(directory)` | `VerificationResult`: recorded-file integrity problems. |

`Tools(soffice=None, verapdf=None, timeout=120)` selects executables and the
per-native-call timeout. Runs take a `Profile` value from `PROFILES`; `source`
performs source/remediation checks, `verify` adds native/PDF/fidelity work, and
`production` also requires veraPDF and rejects warnings. Native-capable use cases
accept `observer=callback`; callbacks receive typed `ProgressEvent` values and
must not raise.

Inspect `AuditRun.reports` and `.failures` separately. Earlier reports survive a
later validator failure. `AuditRun.render("sarif", source_root=...)` refuses partial
SARIF; call `preflight_sarif(sources, source_root)` before expensive work when that
format is required. JSON/text rendering retains completed reports.

Use `Plan.for_source`, `Decision`, registered kinds and `decode_answer` for explicit
programmatic answers, or `load_plan` for reviewed TOML. Rebind permits a different
source digest and still enforces target fingerprints and preservation. A valid
preview has status 0 and `published=False`; refused candidates have status 2.

The executable [examples](../tools/core_examples.py) use only this root surface and
are qualified against an installed wheel outside the checkout. Internal packages
remain importable for advanced callers and carry no compatibility aliases.

Source semantics, measured exporter capabilities, PDF checks, veraPDF, fidelity
and human review remain separate. Recorded-file integrity is not authenticity or
accessibility. See [workflow](WORKFLOW.md), [evidence](EVIDENCE.md) and
[accessibility boundaries](ACCESSIBILITY.md).
