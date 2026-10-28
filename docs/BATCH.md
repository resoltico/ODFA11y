# Batch workflows

Give each source its own reviewed, source-bound [plan](PLAN.md). Create `batch.toml`
alongside sources/plans, then select an [assurance profile](WORKFLOW.md#retain-evidence):

```toml
[[documents]]
id = "annual-report"
source = "sources/report.odt"
plan = "plans/report.toml"

[[documents]]
id = "inventory"
source = "sources/inventory.ods"
plan = "plans/inventory.toml"
```

```sh
odfa11y batch batch.toml --output-dir evidence --profile production
```

Only a nonempty `documents` list is accepted; entries require exactly `id`, `source` and
`plan`. Paths are relative to the manifest, never absolute. IDs are unique ignoring case,
1–64 ASCII letters/digits/underscores/hyphens, starting with a letter/digit. Windows device
names are rejected on every platform. Tool options match [pipeline](CLI.md#batch).

The output root must not exist, even empty or linked. Linked ancestors and inputs inside
the proposed output are refused before creation. Repeated read-only sources/hard-linked
plans are allowed; item destinations stay independent.

Items run sequentially in manifest order. Input, plan, remediation or gate failures retain
item evidence and do not prevent later items. `batch.json` records status, pending IDs,
per-item failed stages and relative evidence references, without source/plan paths.
The strongest [exit outcome](CLI.md#exit-statuses) wins. Each item has an ordinary
[evidence bundle](EVIDENCE.md); verify it with `odfa11y verify evidence/annual-report`.

The summary publishes before execution and atomically updates after each item. Ordinary
CLI SIGINT/SIGTERM retains completed evidence, pending IDs and ordinary cleanup; importing
the API installs no signal handler. Main-thread application calls own cancellation for
their duration. Forced termination or a second signal can prevent cleanup/publication.
Use a fresh root afterward. Native OS isolation and resource limits remain caller duties.

Interactive text progress identifies item IDs/status only. Redirected stderr and JSON
have no progress output. Review every item's `REVIEW.md` before distributing its result.
