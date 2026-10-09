# SARIF reports

Use `--format sarif --source-root ROOT` with `audit` or `compare`. ROOT is
an existing directory containing every source artifact in the report. For example:

```sh
odfa11y audit documents/example.odt --format sarif --source-root . > audit.sarif
```

The output is a SARIF 2.1.0 log with a single run. Registered rules retain their IDs,
severity, categories and configuration remedies. Informational findings use SARIF's
`note` level. Artifact URIs are escaped paths relative to ROOT, including subdirectories
so duplicate basenames remain distinct. ROOT itself is never serialized. Symbolic links
are resolved before containment is checked; a link leaving ROOT is rejected. Comparisons
carry candidate and original artifact identities explicitly, independently of their
display label. Report format 4's internal `sources` references do not appear in JSON.

ODF findings use logical document locations rather than invented XML line numbers.
Package members are diagnostic metadata, not separate source artifacts. Equivalent
packaged and flat documents retain equivalent logical locations. Global findings identify
the artifact without claiming an element or physical line.

SARIF messages use the registered rule title. Free-form finding messages, details,
display labels and report metadata are excluded because they can contain source content,
database credentials or absolute paths from external-tool diagnostics. Use local JSON
or text reports when those detailed diagnostics are needed. Logical labels containing
absolute host paths or URI credentials are rejected. Source-root violations and missing
physical source identities are errors; display labels are never guessed as filenames.
The CLI checks these prerequisites before auditing or exporting any input. SARIF execution
errors use fixed path-free stderr advice to avoid leaking exception paths or tool diagnostics.
A missing root identifies `--source-root` and the requirement that all inputs be files within
it; other execution failures retain generic advice. Rerun with text or JSON output to
investigate detailed local failures. With `--strict`, the CLI also reports the effective
command gate on stderr; the SARIF log remains unchanged.

Generated logs are checked against the unmodified official OASIS draft-07 schema in the
test suite, with negative controls and additional rule-index/artifact-index assertions.
The schema and its notice are test inputs in source distributions; they are not a
runtime dependency or wheel asset. This format does not upload reports to GitHub.
