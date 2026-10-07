# Native document-family fixtures

These invented documents were authored through LibreOffice 26.8.0.3 application services
on macOS. The authoring profile selected **ODF 1.4**, not the producer's extended save
mode. The primary presentation and drawing fixtures validate with zero ODF violations.
`manifest.toml` records their byte identity and producer; the hashes do not replace the
semantic and real-export tests.

Both page documents contain a title, fruit counts, an embedded SVG illustration and an
explicit native navigation order. The illustration intentionally lacks an alternative.
The native PDF export fails the built-in `PDF007` check and veraPDF clause 7.3 test 1.
The explicit library plan supplies the description, page metadata and language; the
production pipeline then passes PDF checks, veraPDF, fidelity and evidence verification.

`sources/page-documents.bas` creates the documents; `sources/fruit.svg` is the invented
graphic. To reproduce them, set `ODFA11Y_FIXTURE_ROOT` to an existing output directory
containing `fruit.svg`, load the BASIC module as `Standard.Module1` in a disposable native
profile, and invoke `macro:///Standard.Module1.Main`. Configure that profile's
`/org.openoffice.Office.Common/Save/ODF/DefaultVersion` to `12`, the native constant for
standard ODF 1.4. Authoring the trusted fixture module also needs macro execution enabled
in that disposable profile. Never apply those authoring settings to a user's profile.

Keep the original producer output. Update the manifest when regenerating, verify the
schema, inspect XML and payloads for private paths, and run the native family integration
tests. Native outputs contain no scripts, external image references or personal author
metadata; the author is `ODFA11y fixture`.
