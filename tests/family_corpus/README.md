# Native document-family fixtures

These invented documents exercise family semantics, preservation and native export
boundaries. [manifest.toml](manifest.toml) is authoritative for producer identity, standard
ODF version, authoring method, stored-byte hashes and expected schema results. Every stored
fixture validates with zero ODF/MathML violations. Hashes identify artifacts; semantic
tests and real exports establish the separate behavioral properties below.

## Fixture contracts

- `fruit-presentation.odp` and `fruit-drawing.odg` contain a title, fruit counts, an
  embedded SVG illustration and explicit native navigation order. The illustration lacks
  an alternative. Their native negative controls require `PDF007` and veraPDF clause 7.3
  test 1. The supplied library plan adds the description, page metadata and language;
  production-pipeline tests then require passing PDF checks, veraPDF, fidelity and bundle
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

Use a disposable LibreOffice profile and an existing output directory. Set
`ODFA11Y_FIXTURE_ROOT` to that directory. For page documents, copy
[sources/fruit.svg](sources/fruit.svg) there. Configure the disposable profile's
`/org.openoffice.Office.Common/Save/ODF/DefaultVersion` to `12`, the native constant for
standard ODF 1.4, and enable macro execution for these trusted fixture modules only.
Never apply these authoring settings to a user's profile.

Load one BASIC source as `Standard.Module1`, invoke `macro:///Standard.Module1.Main`, and
use a separate application run for each module:

- [page-documents.bas](sources/page-documents.bas) creates the presentation and drawing.
- [formula-document.bas](sources/formula-document.bas) creates the formula package.
- [database-document.bas](sources/database-document.bas) creates the invented database.
  This trusted authoring module opens a connection to populate fixture rows.
- [chart-document.bas](sources/chart-document.bas) creates `fruit-chart-source.ods`.
  The standalone Chart fixture requires explicit package assembly: its native
  `Fruit/content.xml`, `styles.xml` and `meta.xml` occupy the package root, with the
  standard Chart mimetype and manifest. The Image fixture likewise uses the drawing's
  native frame and SVG in a standard Image body and package. Neither assembly claims
  direct standalone native save or export support.

Native regeneration reproduces semantics rather than exact bytes. Retain unmodified
native outputs or the explicitly described assemblies, inspect XML and payloads for
private paths, review schema and audit results, and update the manifest deliberately.
Run source-preservation tests and the applicable native family integration tests; a
matching hash cannot replace those checks. Fixtures must contain invented content without
scripts, external image references or personal metadata.
