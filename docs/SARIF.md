# SARIF reports

Confine every input beneath an existing source root:

```sh
odfa11y audit documents/example.odt --format sarif --source-root . > audit.sarif
```

`audit` and `compare` emit one SARIF 2.1.0 run. Registered rule IDs, severity, categories
are retained; informational findings use `note`. Decision-kind references are not emitted. Artifact
URIs are escaped relative paths, preserving distinct subdirectories/basenames. Links
resolve before containment checks; an alias leaving the root is rejected. Comparison
artifacts retain both identities. Physical `Report.sources` remains internal.

[Logical ODF locations](RULES.md#locations) identify objects without invented XML line
numbers. Package members are diagnostics, not separate artifacts. Global findings do not
claim an element location.

Messages use registered rule titles. Free-form messages, details, labels and facts are
excluded because they can contain source content, credentials or absolute diagnostic paths.
Logical labels containing host paths/URI credentials refuse. Source identities are never
guessed from labels. The use case preflights identities before inspection/export; execution failures produce no
partial log. Stderr retains the specific core reason while removing local directories,
credentials and raw diagnostic payloads. Use local JSON/text for fuller diagnosis.
`--strict` changes the effective gate, not the log's contents.

Tests validate against the unmodified official OASIS draft-07 schema and check negative
rule/artifact-index controls. That schema/notice is a source-test input, not a runtime
wheel dependency. Producing SARIF does not upload it anywhere.
