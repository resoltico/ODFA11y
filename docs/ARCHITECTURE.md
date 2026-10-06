# Architecture

The CLI routes operations to separate package, audit, remediation and PDF layers.
All findings use the shared [report model](../src/odfa11y/models.py); rendering and
exit-status policy live in [reporting.py](../src/odfa11y/reporting.py).

```mermaid
flowchart LR
    ODT[Original ODT] --> Audit[Read-only ODT audit]
    ODT --> Edit[Explicit remediation]
    Config[Configuration and CLI choices] --> Edit
    Edit --> Source[Reviewed ODT]
    Source --> Audit
    Source --> Export[LibreOffice export]
    Export --> PDF[PDF]
    PDF --> Inspect[pypdf diagnostics]
    PDF --> Validate[Optional veraPDF validation]
    Audit --> Reports[Audit reports]
    Inspect --> Reports
    Validate --> Reports
```

The diagram shows responsibilities. The combined `pipeline` command gates export on the source audit; see the
[workflow contract](WORKFLOW.md#combined-commands).

## Package boundary

[OdtPackage](../src/odfa11y/odt_package.py) loads ZIP members into memory, retains
archive order and metadata, and parses XML with entity resolution and network
access disabled. [Archive validation](../src/odfa11y/package_archive.py) checks
CRC integrity and the ODT mimetype invariant. Saving writes to a temporary file
in the destination directory, validates it, then replaces the destination.

Member count and declared unpacked size are bounded before decompression. CRC checks
run while reading each member by its ZIP record; rewriting duplicate names is rejected.
These controls establish packaging properties, not a complete untrusted-document sandbox.

## Audit boundary

[ODT audit orchestration](../src/odfa11y/audit.py) delegates package/version,
metadata and semantic checks to focused modules. Audits do not save the source.
Unparseable required members prevent dependent checks; optional schema validation
adds findings from supplied Relax NG validators.

Findings retain a rule ID, severity, message, location, details and `fixable` hint.
[The rule reference](RULES.md) describes the checks. The hint is not an automatic
repair plan or a guarantee that no human input is required.

## Editing boundary

[Remediation](../src/odfa11y/remediate.py) applies explicit options, using separate
metadata and hyperlink helpers. [Configuration loading](../src/odfa11y/config.py)
validates TOML field names and types; [CLI options](../src/odfa11y/cli_options.py)
apply explicit overrides. Unmatched table/graphic identifiers are skipped.

[Style resolution](../src/odfa11y/styles.py) overlays defaults and parent styles
from styles and content XML, stopping inheritance cycles.
[Spacing normalization](../src/odfa11y/spacing.py) creates distinct target styles
instead of globally rewriting the reference or base styles.

The shared [text snapshot](../src/odfa11y/document_text.py) checks normalized
paragraph/heading text before saving. Its precise boundaries and the controlled spacer-removal
exception are documented in [Accessibility and limits](ACCESSIBILITY.md).

## PDF boundary

[Export and validator invocation](../src/odfa11y/pdf_export.py) use argument lists,
subprocess timeouts and a temporary LibreOffice profile. The exported PDF and ODT
are separate outputs; there is no rollback across pipeline stages.

[PDF diagnostics](../src/odfa11y/pdfua.py) read parsed objects with pypdf and securely
parse XMP XML. [Structure inspection](../src/odfa11y/pdf_structure.py) follows the
reachable structure tree, resolves role mappings and checks Figure descriptions.
It does not implement complete PDF/UA conformance; veraPDF supplies separate
machine-validation evidence when explicitly requested.

## Packaging boundary

[pyproject.toml](../pyproject.toml) is the authority for project metadata,
dependencies, lint settings and Hatchling build selection. The version is read
from [the package initializer](../src/odfa11y/__init__.py). There is no `setup.py`
or separate inclusion manifest. See [Development](DEVELOPING.md#packaging) for
source-archive and wheel contents.
