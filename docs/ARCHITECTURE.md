# Architecture

Nine layers separate source meaning, transport, orchestration and presentation. Imports go
down or through declared same-layer edges; [tach.toml](../tach.toml) is the enforced authority.

| Layer | Owners | Responsibility |
| --- | --- | --- |
| L0 foundation | `errors`, `status`, `progress`, `glossary`, `targets`, `contracts`, `capture`, `publish`, language tags/version | Shared meanings, validated contracts, identity and durable publication. |
| L1 infrastructure | `odf`, `native`, `pdf.reading` | Storage, names/styles/resources, bounded native processes and PDF consumption. |
| L2 model | `rules`, `decisions`, `report`, `plans` | Rules, typed answers/targets, producer facts, plans and machine formats. |
| L3 checks | `concepts`, `pdf` | Cross-family source semantics, preservation, PDF structure/validation/fidelity. |
| L4 families | `families` | Eight frozen specs, audits, kinds, edits and doctor-only experiments. |
| L5 workflows | `audit`, `remediate` | Source questions, decision compilation and guarded in-memory candidates. |
| L6 runs | `run`, `batch`, `evidence` | Artifact-dependent stages, immutable records/review and generic bundles. |
| L7 application | One module per use case, `Tools`, `NativeTools` | Public preparation, required tools, captures and result contracts. |
| L8 presentation | `cli` | Arguments, text, terminal escaping, progress display and one output writer. |

The CLI imports only the root API, stdlib and itself. Families never import one another;
concepts never import families. PDF and native packages never import each other. Lower
layers never import application. No cycles or temporary layer exceptions remain.

## Source and decisions

A use case captures each input once into a private directory and opens one `OdfDocument`.
Cached trees preserve validated structure. Full content checkpoints include namespace
bindings and invalidate derived analyses after mutation; storage changes behind a cached
tree refuse. The [model](../src/odfa11y/odf/document.py) owns this lifetime.

`FamilySpec` supplies its audit, kinds, export contract, language access and doctor probes.
A single style resolver takes explicit scope/family; [XML names](../src/odfa11y/odf/names.py)
have one owner. `DecisionKind[A]` owns the answer, direct edit, target domain and resolved
rules. Questions are created with raised findings. Target domains own enumeration,
resolution and fingerprints; content answers remain target-bound.

Edits return outcomes plus an `Allowance`. One
[preservation proof](../src/odfa11y/concepts/preservation.py) masks only those declared effects.
Protected/opaque content and schema-regression controls remain independent. The executor
returns a guarded `Candidate` or refusal without capturing or publishing. Application
publication is explicit; low-level editing does not implicitly execute those guards.

## Runs and native transport

Preparation loads/binds plans and resolves required tools before user output. A source audit
establishes the readable-source artifact. Each field in `RunState` has one producer. The
[stage table](../src/odfa11y/run/stages.py) declares minimum profiles and required artifacts;
failed finding gates retain artifacts, while refusals supply none. Records are derived at
the end. Batch preparation failures are summary errors, not fabricated runs.

Native runners receive resolved executable/identity values. veraPDF returns original report
bytes and identity; PDF code parses them independently. Family experiments compose native
and PDF observations, run only in doctor and never gate document runs or share a batch cache.

All PDF stream access goes through the bounded reader. One Form walk and shared object
helpers feed typed inspection results; fidelity retains immutable snapshots and declared
image artifacts. Incomplete or malformed inspection never becomes a clean measurement.

## Delivery

`publish.py` owns staged writes, sync and explicit replacement/no-clobber policy. Generic
evidence imports no run/family code and publishes only declared artifacts; its manifest
owns hashes. Run-owned `REVIEW.md` starts with human work and observed topics, then facts.
The nine frozen results use one Annotated-contract engine for validation, serialization and
[schemas](SCHEMAS.md). The CLI renders those facts, with stdout/stderr confined to its writer.

[Development](DEVELOPING.md) describes the one corpus, check entry point, clean minimal
builds and installed-wheel qualification. [Accessibility](ACCESSIBILITY.md) owns guard and
human-acceptance limits; these mechanisms do not sandbox native applications.
