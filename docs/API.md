# Application API

Import `odfa11y` for the nine use cases. Every result is frozen, has `as_dict()` and owns
its derived `exit_status`. Core calls produce no terminal output and importing the root
does not import the CLI. Preparation and execution can raise the documented error classes;
see [exit meanings](GLOSSARY.md#exitstatus).

```python
import odfa11y as api

checks = api.audit(["original.odt"], schema=True)
questions = api.plan("original.odt")
# Review questions.template and save answered fields in plan.toml.
record = api.run("original.odt", "plan.toml", "evidence", profile=api.Profile.PDF)
integrity = api.verify_evidence("evidence")
```

| Use case | Result |
| --- | --- |
| `audit` | `AuditResult`: input reports, failures, plannability and combined acceptance. |
| `plan` | `PlanResult`: source report and an optional bound unanswered template. |
| `remediate` | `RemediationResult`: outcomes, predictions, violations, schema and publication state. |
| `export` | `ExportResult`: published PDF; validation remains a separate request. |
| `compare` | `ComparisonResult`: fidelity report, strict flag and effective acceptance. |
| `run` | `RunRecord`: profile, typed stage outcomes, decisions and established facts. |
| `batch` | `BatchRecord`: recorded profile, item outcomes, pending IDs and evidence references. |
| `verify_evidence` | `VerificationResult`: file-integrity problems, independent of accessibility. |
| `doctor` | `DoctorResult`: tool identities, scoped measurements and unavailable operations. |

`Tools` selects LibreOffice, veraPDF and the single per-native-call timeout. Tools are
resolved only when required. Use `Profile.SOURCE`, `Profile.PDF` or `Profile.PRODUCTION`;
production alone rejects warnings and requires independent validation. `NativeTools` is
the explicit seam for native execution and test fakes.

Recognizable ODF containers with unsupported media types retain package/structure findings;
planning and edits remain unavailable. Unrelated inputs are refused.

Audit JSON always contains an `inputs` array, for one or several sources. It is exactly
`AuditResult.as_dict()`, not a conditional report/object array. Each input retains completed
reports through later failures and exposes core-owned `plannable`. Progress observers receive
fixed steps and terminal states, with batch item IDs, and must not raise.

For SARIF, pass `SarifOptions(source_root)` to `audit(..., sarif=options)` or
`compare(..., sarif=options)`, then render `result.as_sarif(options)`. This preflights identities
before work and refuses partial logs. `render_json` and `render_sarif` are machine renderers;
text and terminal escaping belong to the CLI. See [SARIF](SARIF.md).

`registered_kinds()` provides typed answer constructors. Build `Decision(kind, target, answer)`
and a source-bound `Plan.for_source`; target decisions require the current domain binding.
`plan(source, from_plan=previous)` prepares a newly bound plan and carries only matching
answers. [Executable examples](../tools/core_examples.py) use this root surface and qualify
an installed wheel outside the checkout. Low-level model/native calls leave guard policy,
publication and native isolation to their caller.
