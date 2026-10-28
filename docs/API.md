# Public library operations

The installed-package examples in [core_examples.py](../tools/core_examples.py) cover audit,
styles, templates, explicit remediation, partial diagnostics, export, comparison and evidence.
`inspect_source()` demonstrates text-family edits; `native_work()` returns fidelity, a run
record and bundle-integrity problems, which require separate inspection. Run outside the
checkout in an isolated installed-wheel environment; see [Development](DEVELOPING.md).

Core operations neither import the CLI nor print terminal output. Applications choose
rendering, JSON/SARIF serialization and strict warning policy.

| Entry point | Inputs/result | Ownership and failure |
| --- | --- | --- |
| `pipeline.audit_document` | Regular ODF/PDF path; iterator of `Report`; optional schema/PDF validation and timeout. | Read-only; starts on iteration. Consume incrementally to keep completed reports if a later validator fails. Stopping early omits checks. |
| `audit.prepare_plan` | ODF path; `(Report, commented TOML or None)`. | Read-only. Unreadable, encrypted, ambiguous or unsafe inputs yield blockers; templates choose no meaning. |
| `families.style_usage` | ODF path; style-usage rows. | Read-only. Unsupported families/blocked inspection raise `UnsupportedKindError`; storage/OS failures can propagate. |
| `remediation.remediate` | Distinct source/destination, source-bound Plan, optional dry run/rebind; `RemediationResult`. | Guards package inspection, family/protected-content/schema contracts; publishes atomically only on success. Refused candidates return published=false and exit_status=2; valid previews return published=false and exit_status=0. Source-binding failures raise PlanError. |
| `pipeline.export_document` | Original ODF, PDF destination, optional `NativeOptions`; published `Path`. | Guarded original export preserves logical identity. Caller chooses executables and stable source/resource directories. |
| `pipeline.compare_documents` | Original ODF/PDF inputs, policy, optional diffs/options; `Report`. | Guards native inputs, owns temporary renders/profile through comparison, preserves requested diffs. Fidelity is not accessibility. |
| `pipeline.inspect_tools` | Optional `NativeOptions`; `(partial identity facts, controlled probe error or None)`. | Can run bounded identity/capability probes; inspect both values. Version/capability is not document conformance. |
| `pipeline.run_pipeline` | Source, Plan, absent/empty destination, optional `PipelineOptions`; `RunRecord`. | Records domain/OS stage failures and skips, publishing evidence when safely writable. Inspect `exit_status`, stages and required review. Unsafe destination/publication failures may raise. |
| `evidence.check_bundle` | Bundle directory; list of integrity problems. | Read-only static unsafe-path/hash checks. Bundle/ancestor namespace must stay stable. Integrity is not authenticity/review. |

Expected domain failures use `OdfA11yError` subclasses: `PlanError` for invalid choices
(including invalid timeout values), `PackageError` for unreadable inputs,
structured remediation violations for refused edits/postconditions, `UnsupportedKindError` for unavailable
family/native contexts, and `ToolError` subclasses for native failures, including elapsed
tool deadlines. Ordinary filesystem errors can propagate. Audit generators can raise while
consumed. There is no universal result wrapper; respect each operation's error boundary.

`NativeOptions` supplies native settings; `PipelineOptions` also selects assurance profile.
Observers are optional synchronous callbacks with typed ProgressEvent values and no document
payload/paths. They must not raise. Display labels are not a frozen machine protocol;
observers do not affect execution identity or persisted evidence. Rendering elsewhere
keeps machine JSON/SARIF clean.

## Guarded and caller-owned surfaces

`OdfDocument.tree()` returns mutable cached XML. Content checkpoints drive change accounting
and cache invalidation; `save()` serializes changed trees automatically. Stored XML cannot
replace an already cached tree: reopen after low-level storage replacement. Direct storage,
`save()` and `Operation.apply()` remain caller-owned surfaces; root remediation owns the
preservation and publication guards.
They do not imply executor safeguards or whole-plan atomicity. Multi-target operations
preflight their own targets; guarded `remediate()` enforces final preservation/schema and
atomic publication across the plan.

`pdf.export_pdfua()` is a raw native boundary. Its caller establishes resource/protection
policy and OS isolation. Guarded `export_document()`, `compare_documents()` and
`run_pipeline()` establish the shared declaration policy; they still do not sandbox native
tools. Direct original export/comparison preserve logical identity; pipeline capture has
its own [identity/stable-directory contract](EVIDENCE.md#source-capture).

Duplicate/unsafe package names block guarded planning, remediation and native work before
manifest/body selection. Signatures, encryption, tracked changes and excluded contexts
have explicit [preservation boundaries](ACCESSIBILITY.md#preservation-boundaries).
Graphic/page/link metadata uses reviewed structural/style identities; detached pages do
not establish style dependencies. `content.page_fingerprint(page, document)` requires the
`OdfDocument`; see [reviewed identities](PLAN.md#decision-plans).

Source semantics, exporter capability, PDF audit/veraPDF, fidelity and human review remain
separate. Production requires veraPDF and fails warnings. Missing tools and skipped stages
are not passing validation; inspect [Workflow](WORKFLOW.md),
[Accessibility](ACCESSIBILITY.md) and [Evidence](EVIDENCE.md).
