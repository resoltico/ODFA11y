# Public library operations

The executable examples in [core_examples.py](../tools/core_examples.py) use the installed
package's public imports. They cover incremental audit, styles, template preparation,
explicit remediation, partial diagnostics, export, comparison and the evidence pipeline.
`inspect_source()` demonstrates supported text-family source edits. `native_work()` returns
fidelity, the pipeline record and bundle integrity problems; inspect all three independently.
Run them outside the source checkout with a wheel installed in an isolated environment;
see [Development](DEVELOPING.md) for the distribution checks. Core operations neither import
the CLI nor print terminal output. Applications choose rendering, JSON/SARIF serialization
and strict warning policy themselves.

| Entry point | Inputs and result | Ownership and failure |
| --- | --- | --- |
| `pipeline.audit_document` | Regular ODF/PDF path; iterator of `Report` objects. Optional schema and PDF validation, selected timeout. | Read-only. Work begins on iteration. Consume incrementally to keep completed reports if a later validator fails; stopping early omits remaining checks. |
| `audit.prepare_template` | ODF path; `(Report, commented TOML or None)`. | Read-only; unreadable/encrypted input produces blockers rather than usable decisions. Templates never choose meaning or enable guesses. |
| `families.style_usage` | ODF path; list of style usage rows. | Read-only; families without paragraph-style inspection raise `UnsupportedKindError`; parsed storage and OS errors propagate. |
| `remediation.remediate` | Distinct source/destination, explicit operations and optional dry run; `RemediationResult`. | Atomically publishes only after guards, protected-content and schema checks. Failure preserves existing destination. Dry run publishes nothing. |
| `pipeline.export_document` | ODF path, PDF destination and `NativeOptions`; published `Path`. | Guarded original native export retains source identity. Caller owns executable selection and stable source/resource directories. |
| `pipeline.compare_documents` | Original ODF/PDF paths, fidelity policy, optional diff directory/options; `Report`. | Temporary renders are cleaned; requested diff artifacts remain. Fidelity does not establish accessibility. |
| `pipeline.inspect_tools` | Optional `NativeOptions`; `(partial identity facts, controlled probe error or None)`. | May run bounded tool identity/capability probes; callers must inspect both values. An identity is not document conformance. |
| `pipeline.run_pipeline` | Source, operations, policy, empty/new evidence directory and `PipelineOptions`; `RunRecord`. | Converts stage failures to recorded failure/skip states and publishes evidence when its destination remains writable. Inspect `record.exit_status`, each stage and human review; successful integrity is not a passing gate. |
| `evidence.check_bundle` | Bundle directory; list of integrity problems. | Read-only static unsafe-path checks. Bundle and ancestor directory namespace must remain stable throughout verification. Hashes establish integrity against the manifest, not authenticity or review. |

Expected failures use `OdfA11yError` subclasses: `ConfigError` for invalid choices and native
timeouts, `PackageError` for unreadable input, `RemediationError` for unsupported edits or
failed postconditions, `UnsupportedKindError` for unavailable family/native contexts and
`ToolError` for native execution failures. Ordinary filesystem errors may also propagate.
The audit generator can raise during consumption. Pipeline stage-domain/OS failures become
recorded execution failures; unsafe evidence destinations or publication failures may raise.
There is no universal result wrapper; use each documented result and error boundary.

Observers are optional synchronous callbacks receiving fixed progress labels/statuses,
without document payload or paths. They must not raise. They are presentation hooks, excluded
from execution identity, and their current display labels are not a frozen machine protocol.
Machine JSON and SARIF remain clean when observers render elsewhere.

`OdfDocument.tree()` reads cached XML. Mutable storage, `edit()`, `save()` and direct
`Operation.apply()` are caller-owned low-level surfaces. They do not imply the guards of
`remediate()`. Similarly `pdf.export_pdfua()` is a raw native boundary: callers must establish
resource/protection policy and native OS isolation. The supported guarded alternatives are
`remediate()` and `export_document()`/`compare_documents()`/`run_pipeline()`.

Source semantics, actual exporter behavior, PDF inspection/veraPDF, fidelity and human review
remain separate conclusions. The production profile fails strict warnings and requires
veraPDF; missing tools or skipped stages are never a passing validation. See
[Accessibility](ACCESSIBILITY.md), [Workflow](WORKFLOW.md) and [Evidence](EVIDENCE.md).
