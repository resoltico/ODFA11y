# Writer regression corpus

Small documents authored by a real LibreOffice Writer, used to test ODFA11y against what
Writer actually writes rather than against the synthetic documents of `tests/documents.py`.
All content is invented for this corpus and released with the project under MPL-2.0.

[manifest.toml](manifest.toml) is the authority for each document's expected audit rule ids
(`rules`), the rule ids left after the standard remediation plan (`rules_after_plan`), the
number of ODF schema violations Writer's own output has (`schema_violations`) and the SHA-256
of its bytes. The tests in `tests/test_corpus*.py` check all of it, so a change to a document
or to a rule fails a test until the manifest is deliberately updated.

## Provenance

LibreOffice 24.2.7.2 (420, Build:2) on Linux, run headless by [build.sh](build.sh) from the
files in [sources/](sources/): Writer imports each HTML or flat-XML source and saves it as a
package (`.odt`), and for five documents also as flat XML (`.fodt`). Nothing is edited by hand
after Writer saves it. Every document declares ODF 1.3, as Writer 24.2 writes it.

Writer's output is not schema-valid ODF: every document has violations against the bundled
ODF schema (LibreOffice-specific style properties), which the manifest records. Flat files
report fewer violations than the package of the same document because libxml2 stops at the
first error of a failing content model; the tests only require both forms to agree on validity.

## Documents

Each purpose below belongs to the document named; a name listed with both extensions exists as
a package and as flat XML, and the two must audit identically.

| Document | Purpose |
| --- | --- |
| `bookmarks.odt` | Heading bookmarks and an internal link to one; a clean baseline. |
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
| `table-no-header-row.odt` | A data table without a header row. |

Writer's HTML import leaves an empty paragraph after a table, so the three table documents
also report the spacer rule. No document contains tracked changes; a test checks that.

## Change the corpus

See [Developing](../../docs/DEVELOPING.md#writer-regression-corpus).
