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
stage. The overall exit status is the strongest result: execution failure 3, audit errors
2, strict warnings 1, or success 0.

The summary is published before execution and atomically replaced after each item.
SIGINT and SIGTERM mark an active run `interrupted`, retain completed item evidence and
identify unrun entries. A forced kill or power loss can leave `running` evidence: it is
explicitly incomplete, never a completed result. Forced termination on Windows does not
permit an interruption handler to run. Resume is not implicit; inspect retained evidence
and create an explicit manifest and a fresh destination for remaining items.

Standalone CLI commands and batch translate ordinary SIGTERM/SIGINT into controlled
interruption so the active external tool tree is cleaned up where the platform allows it.
The previous SIGTERM policy is restored when the scope ends; importing or embedding the
tool runner does not install a handler. Windows forced termination, SIGKILL and power loss
can bypass cleanup and summary publication. Completed item bundles remain independently
verifiable; interrupted staging directories are not published evidence. There is no implicit
recovery or automatic resumption. OS isolation and resource limits remain caller duties.
