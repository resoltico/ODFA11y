# Native reproductions

These invented documents provide native checks for text contexts and link descriptions.
They contain no customer content or actual person's information.

## Text contexts

`text-contexts.fodt` is the source for `text-contexts.odt`. It contains a main heading,
stored tracked deletion, a note, an annotation, a conditional section, authored
link/bookmark/field content and ODF space/tab/line-break separators. The package's
generator metadata identifies LibreOffice 26.8.1.1.

Generate a package with a disposable profile and a separate output directory:

```sh
soffice -env:UserInstallation=file:///absolute/private/profile --headless \
  --convert-to odt --outdir /absolute/output tests/reproductions/text-contexts.fodt
```

Native output has bundled-schema violations. Tests compare the actual before/after
schema result, protect excluded XML exactly and check rendered word boundaries after
metadata remediation and native export. The main heading contributes to the live outline;
stored deletion and note headings do not. The deleted heading is absent from PDF text,
while the note heading remains readable. These checks establish preservation and context
behavior, not ODF or PDF/UA conformance.

Regeneration reproduces source semantics, not exact package bytes. Inspect generated XML,
metadata, schema results and native test outcomes before replacing the stored fixture.

## Link descriptions

`unnamed-link.odt` is a schema-valid document with one hyperlink and no `office:name`.
The native regression requires `PDF019` and failed veraPDF link-description checks.
Its independent positive control adds `office:name="Example site"`, then requires passing
PDF checks, veraPDF and the evidence pipeline. The controls measure Writer's behavior;
automatic remediation does not repurpose target names as descriptions.
