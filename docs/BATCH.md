# Batch workflows

Run an explicit set of documents through the same pipeline and assurance profile as a
single-document run. Each document has its own reviewed configuration; batch execution
never selects a plan or invents remediation decisions.

Create `batch.toml` alongside the source documents and plans:

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
odfa11y batch batch.toml --output-dir evidence --profile inspect
```

Use `--profile verify` for native export and built-in PDF/fidelity gates, or
`--profile production` for strict warnings and required veraPDF validation. Tool selection
uses the same `--soffice`, `--verapdf-path` and `--timeout` options as `pipeline`.
`--format json` prints the batch summary.

Text summaries include the profile, aggregate exit status and each item's failed
stage and relative evidence reference. Interactive text progress reports item IDs
and status only; it exposes no source or plan paths. Redirected stderr and JSON
commands have no progress output. A completed batch means its selected automated
gates completed; inspect each item's `REVIEW.md` for required human review.

The manifest accepts only a nonempty `[[documents]]` list. Each entry requires exactly
`id`, `source` and `plan`. Source and plan paths are relative to the manifest directory;
absolute paths are rejected. IDs contain 1–64 ASCII letters, digits, underscores or
hyphens, start with a letter or digit, and must be unique ignoring case. Windows reserved
device names are rejected on every platform.

The output root must not exist, including as an empty directory or symbolic link.
Symbolic links in its ancestor path and inputs within the proposed output are rejected
before any output is created. Repeated read-only sources and hard-linked plans are
allowed; they never share an evidence destination. Items run sequentially in manifest
order. An unreadable source, invalid plan, failed remediation or failed gate produces
failure evidence and does not prevent later items from running.

`evidence/batch.json` records status, exit status, pending IDs and per-item status,
failed stage and relative evidence directory. It contains no source or plan paths.
Each item directory is the ordinary atomic pipeline bundle, including `run.json`,
`REVIEW.md` and a hash manifest; `odfa11y check-evidence evidence/annual-report` verifies
its integrity. Invalid plans produce the same bundle structure with a failed `load-plan`
stage. The overall exit status is the strongest result: execution failure 3, usage error 4, audit errors
2, strict warnings 1, or success 0.

The summary is published before execution and atomically replaced after each item.
Ordinary CLI SIGINT/SIGTERM interrupts active work, cleans up its external tool tree where
the platform permits, retains completed item evidence and identifies unrun entries. Importing
the runner installs no signal handler. Main-thread CLI and direct `run_batch()` execution
can temporarily replace SIGTERM handling and restore the caller's policy afterward;
non-main-thread execution installs no handler.

SIGKILL, Windows forced termination, power loss and escaped descendants can bypass cleanup
or summary publication. A retained `running` state is incomplete, never a completed result;
interrupted staging directories are not published evidence. Completed bundles remain
independently verifiable. There is no implicit resume: inspect retained evidence, create an
explicit manifest for remaining items and use a fresh output root. OS isolation/resource
limits remain caller duties.
