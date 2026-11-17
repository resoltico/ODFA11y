# Native document-family fixtures

These invented documents exercise family semantics, preservation and native export
boundaries. [unified manifest](../manifest.toml) is authoritative for producer identity, standard
ODF version, authoring method, stored-byte hashes and expected schema results. Every stored
fixture validates with zero ODF/MathML violations. Hashes identify artifacts; semantic
tests and real exports establish the separate behavioral properties below.

## Fixture contracts

- `fruit-presentation.odp` and `fruit-drawing.odg` contain a title, fruit counts, an
  embedded SVG illustration and explicit native navigation order. The illustration lacks
  an alternative. Their native negative controls require `PDF008` and veraPDF clause 7.3
  test 1. The supplied library plan adds the description, page metadata and language;
  production run tests then require passing PDF checks, veraPDF, fidelity and bundle
  verification.
- `sum-formula.odf` contains native MathML and its StarMath annotation. Supplying a spoken
  alternative preserves the expression and annotation. Native Math export fails
  required tagging and veraPDF; a valid source does not establish PDF accessibility.
- `fruit-chart.odc` contains native Calc internal-data-provider chart parts in a standard
  Chart package. It exercises source data, range, metadata and preservation checks.
- `fruit-image.odi` contains a native Draw frame, geometry and embedded SVG under the
  standard `office:image` body. It exercises source descriptions, payload integrity and
  preservation. Chart and Image have source-only library assurance, with no native PDF
  export contract or conversion shim.
- `fruit-database.odb` contains embedded Firebird storage with invented `Fruit` rows
  Apples/3 and Pears/4. Optional metadata and styles parts are absent. Explicit metadata
  remediation creates the standard part while protecting embedded bytes and settings.
  Library inspection and remediation never open a database connection.

## Sources and regeneration

Use the [single builder](../../../tools/build_corpus.py) with `--purpose family-conformance`
and a new output directory. It installs the trusted modules below only in disposable
profiles, selects standard ODF 1.4 and binds the output directory. No user's profile is changed.

The retained sources explain each native operation:

- [page-documents.bas](sources/page-documents.bas) creates presentation and drawing inputs.
- [formula-document.bas](sources/formula-document.bas) creates the formula package.
- [database-document.bas](sources/database-document.bas) populates invented database rows.
- [chart-document.bas](sources/chart-document.bas) creates a native internal-data-provider chart.

Chart and Image require explicit standard-package assembly from native Calc/Draw parts;
the builder performs that assembly without claiming direct standalone save/export support.

Native regeneration reproduces semantics rather than exact bytes. Retain unmodified
native outputs or the explicitly described assemblies, inspect XML and payloads for
private paths, review schema and audit results, and update the manifest deliberately.
Run source-preservation tests and the applicable native family integration tests; a
matching hash cannot replace those checks. Fixtures must contain invented content without
scripts, external image references or personal metadata.

`sheet-values.ods` and `sheet-references.ods` are synthetic ODF fixtures for the preservation matrix, not native-save measurements. Both contain values, header rows, a hidden sheet and an embedded PNG; the latter also has a formula referencing the first sheet.
