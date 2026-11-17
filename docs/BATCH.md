# Batch workflows

Give every source its own reviewed [plan](PLAN.md). Paths in `batch.toml` are relative to
that batch file:

```toml
[[documents]]
id = "report"
source = "sources/report.odt"
plan = "plans/report.toml"
```

```sh
odfa11y batch batch.toml --output-dir batch-evidence --profile pdf
```

The nonempty list requires exactly `id`, `source` and `plan` in each item. IDs are unique
ignoring case, 1–64 ASCII letters/digits/underscores/hyphens and start with a letter/digit.
Windows device names and unsafe/absolute paths refuse on every platform. See the generated
[batch command](CLI.md#batch).

The output root must not exist, even empty or linked. Linked ancestors and inputs inside
the proposed output refuse before creation. Repeated read-only sources and hard-linked
plans are allowed. Items execute serially with independent captures and destinations.

`batch.json` records the selected profile, lifecycle, pending IDs, item exit statuses,
failures and relative evidence references. A preparation failure appears there alone:
there is no item bundle or fabricated run. Successfully prepared items are ordinary
[runs](EVIDENCE.md), including evidence for later gate failures. The strongest
[exit outcome](CLI.md#exit-statuses) wins; failure of one item does not stop the others.

The summary publishes before execution and atomically after transitions. CLI SIGINT/SIGTERM
retains completed evidence and pending IDs. Library calls install no signal handler and
propagate interruption; callers own cancellation. Forced termination or a second signal
can prevent cleanup/publication. Use a new root afterward.

Progress events carry each item ID and fixed inner steps. Progress is interactive text
stderr only. JSON prints exactly `BatchRecord.as_dict()`. Verify existing item bundles with
`odfa11y verify-evidence batch-evidence/report`, then perform their human reviews.

Required native tools and identities resolve once per batch, after the first valid item plan.
Later items reuse that result, including a tool failure; each item still prepares independently.

Completed Python batch items expose their read-only `stages` tuple for inspection and text
rendering. `batch.json` remains a summary; full run records stay in each item’s evidence bundle.
