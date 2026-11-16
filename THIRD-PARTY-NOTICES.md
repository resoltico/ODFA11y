# Third-party licensing

ODFA11y's owner code is [AGPL-3.0-only](LICENSE). Third-party material keeps its own terms;
[commercial licensing](LICENSE-COMMERCIAL.md) cannot waive another rights holder's conditions.
The Python wheel does not bundle its separately installed Python dependencies, LibreOffice or
veraPDF. Their own distributions supply their notices and license texts. Retain those texts
when redistributing an environment or executable that includes them.

## Material shipped in this repository and package

| Material | Terms and authoritative notice |
| --- | --- |
| Unmodified OASIS ODF schemas | [OASIS notices](src/odfa11y/odf/schemas/NOTICE.txt); copy with notices and do not modify the standards themselves. [Provenance](src/odfa11y/odf/schemas/PROVENANCE.toml) identifies exact upstream bytes. |
| Unmodified MathML grammar modules | [W3C Software Notice and License](src/odfa11y/odf/schemas/mathml/NOTICE.txt); preserve notices and disclaimers. |
| OpenFormula reference data | [OASIS notice](src/odfa11y/odf/formula_data/NOTICE.txt); preserve the notice and source attribution. |
| SARIF test schema, contributor source only | [OASIS notice](tests/data/sarif/NOTICE.txt); not installed in the Python wheel. |

These standards/reference files are separate data and retain their original licenses; they
are not relicensed as owner code. The package license expression names their terms alongside
the owner license.

## Runtime dependencies

| Dependency | Upstream terms and redistribution considerations |
| --- | --- |
| [lxml](https://github.com/lxml/lxml/blob/master/LICENSES.txt) | BSD-3-Clause owner code, plus ElementTree/PSF and resource notices. Binary wheels include native libraries under MIT, zlib and, where present, LGPL-2.1 libiconv terms. Preserve the selected wheel's `LICENSE.txt` and `LICENSES.txt`; LGPL components retain their source/relinking rights even in a separately licensed commercial product. |
| [Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE) | MIT-CMU plus bundled-library notices in its installed `LICENSE`. Wheel features can include FreeType, LittleCMS, image codecs and compression libraries. Use FreeType's permissive FTL option with its required attribution when applicable. |
| [pypdf](https://github.com/py-pdf/pypdf/blob/main/LICENSE) | BSD-3-Clause; retain copyright, conditions and disclaimer. |
| [pypdfium2 and PDFium](https://pypdfium2.readthedocs.io/en/stable/readme.html#licensing) | pypdfium2 offers Apache-2.0 or BSD-3-Clause; PDFium uses BSD-style terms. Preserve the installed wheel's PDFium and `BUILD_LICENSES` texts for bundled native libraries. Its documentation/examples have separate CC-BY-4.0 terms. Exact native terms depend on the selected platform/build; any GCC runtime components retain their runtime-library exception conditions. |

The permissive runtime components can be used with AGPL-3.0-only and in commercial products
while retaining their notices and conditions. LGPL components do not prevent commercial use,
but impose their own obligations when conveyed; an ODFA11y commercial agreement does not
remove them. Check the exact dependency artifacts when packaging a different platform, custom
native build or self-contained application. A Python dependency identifier alone does not
identify all libraries inside its wheel.

## External applications and contributor tools

LibreOffice and veraPDF are separate executables invoked through their command-line
interfaces, not included in ODFA11y's wheel. LibreOffice provides its
[licensing information](https://www.libreoffice.org/about-us/licenses/); veraPDF provides its
[MPLv2+ / GPLv3+ licensing choices](https://github.com/veraPDF/veraPDF-library#license).
Keep their own distributions and notices intact if supplying them with a product; this
project's license and commercial direction do not relicense them.

Build, test and analysis tools are separate development dependencies declared in
`pyproject.toml` and pinned in `uv.lock`. They are not linked or copied into the installed
ODFA11y package. Their own licenses continue to govern their use and any redistribution of
a development environment; listing them in a lockfile does not sublicense their code.
