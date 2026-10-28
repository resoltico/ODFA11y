# Writer regression corpus

Small, invented LibreOffice Writer documents exercise ODFA11y against native producer
output alongside the synthetic documents in `tests/fixtures/documents.py`. Their content is
released with the project under MPL-2.0.

[manifest.toml](manifest.toml) identifies the producer and records each stored document's
expected audit rule IDs (`rules`), remaining rule IDs after the standard remediation plan
(`rules_after_plan`), bundled-schema violation count (`schema_violations`) and SHA-256.
The tests in `tests/application/test_corpus.py` and
`tests/application/test_corpus_remediation.py` verify those expectations and byte identities. Hashes
identify the stored artifacts; they do not establish semantic correctness.

## Sources and validation

[build.sh](build.sh) imports the HTML and flat-XML files in [sources/](sources/) through
Writer and saves packages (`.odt`), with five documents also saved as flat XML (`.fodt`).
The stored documents are unmodified Writer output and declare ODF 1.3. The producer
identity in the manifest describes these fixtures, not a supported execution runtime.

Every stored document has violations against the bundled ODF schema, including
LibreOffice-specific style properties. Package and flat forms can have different
diagnostic counts because libxml2 stops at the first error of a failing content model.
Tests require paired forms to agree on audit findings, visible words and schema validity;
the manifest records the diagnostic count for each file separately.

## Documents

Each purpose below belongs to the named document. A name with both extensions has package
and flat forms.

| Document | Purpose |
| --- | --- |
| `bookmarks.odt` | Heading bookmarks and an internal link to one; a clean semantic-audit baseline. |
| `footnotes.odt`, `footnotes.fodt` | Two footnotes; reading order needs manual review. |
| `frames-textbox.odt` | A floating text box anchored to a paragraph. |
| `header-footer.odt`, `header-footer.fodt` | A running header and a footer with a page number. |
| `headings-skipped.odt` | Heading levels 1, 3 and 5 with no level 2 or 4. |
| `images-described.odt` | Pictures with title and description, title only, description only. |
| `images-undescribed.odt`, `images-undescribed.fodt` | A picture with neither title nor description. |
| `links.odt`, `links.fodt` | Inline and line-wrapping hyperlinks, an e-mail address and a URL left as plain text. |
| `lists-nested.odt` | Bulleted and numbered lists nested three levels deep. |
| `mixed-languages.odt` | German and French phrases and a Latvian paragraph in an English document. |
| `page-breaks-spacers.odt` | Two empty spacer paragraphs and a page break set on a paragraph style. |
| `table-header-row.odt` | A table with a repeating header row. |
| `table-merged-cells.odt`, `table-merged-cells.fodt` | A table with cells merged across and down. |
| `table-no-header-row.odt` | An untyped table without a header row; its data/layout intent requires review. |

Writer's HTML import leaves an empty paragraph after a table, so the three table documents
also report the spacer rule. Tests verify that no document contains tracked changes.

## Regenerating

Follow [Developing](../../docs/DEVELOPING.md#native-document-fixtures). Native regeneration
reproduces document semantics, not exact bytes: generated metadata and producer choices
can change the output. Review the documents, audit findings and schema results before
updating the manifest's identities and expectations. Keep source changes, retained native
outputs and the filename inventory above consistent.
