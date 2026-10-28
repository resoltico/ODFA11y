# SPDX-License-Identifier: MPL-2.0
"""Author invented Writer structure fixtures through the installed LibreOffice converter."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from odfa11y.native.export import find_soffice, identify_soffice
from odfa11y.native.process import run_bounded
from odfa11y.odf import OdfDocument, validate
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.table_formats import NUMERIC_STYLES

ROOT = Path(__file__).resolve().parents[1] / "tests/text_corpus"
LIST_STYLE = (
    '<text:list-style style:name="FruitList">'
    '<text:list-level-style-number text:level="1" style:num-format="1"/>'
    '<text:list-level-style-number text:level="2" style:num-format="a"/></text:list-style>'
)
CASES = {
    "tables-data-no-headers": (
        (
            '<office:text><table:table table:name="Data">'
            '<table:table-column table:number-columns-repeated="2"/>'
            "<table:table-row><table:table-cell><text:p>Fruit</text:p></table:table-cell>"
            "<table:table-cell><text:p>Amount</text:p></table:table-cell></table:table-row>"
            "<table:table-row><table:table-cell><text:p>Apples</text:p></table:table-cell>"
            '<table:table-cell table:style-name="Numeric" '
            'office:value-type="float" office:value="3"><text:p>3</text:p>'
            "</table:table-cell></table:table-row></table:table></office:text>"
        ),
        NUMERIC_STYLES,
    ),
    "tables-positive": (
        (
            '<office:text><table:table table:name="Fruit">'
            '<table:table-column table:number-columns-repeated="3"/>'
            "<table:table-header-rows><table:table-row>"
            '<table:table-cell table:number-columns-spanned="2"><text:p>Fruit categories</text:p>'
            "</table:table-cell><table:covered-table-cell/>"
            "<table:table-cell><text:p>Quantity</text:p></table:table-cell></table:table-row>"
            "<table:table-row><table:table-cell><text:p>Name</text:p></table:table-cell>"
            "<table:table-cell><text:p>Colour</text:p></table:table-cell>"
            "<table:table-cell><text:p>Total</text:p></table:table-cell>"
            "</table:table-row></table:table-header-rows><table:table-row>"
            "<table:table-cell><text:p>Apples</text:p></table:table-cell>"
            "<table:table-cell><text:p>Red</text:p></table:table-cell>"
            '<table:table-cell table:style-name="Numeric" '
            'office:value-type="float" office:value="3"><text:p>3</text:p>'
            "</table:table-cell></table:table-row></table:table></office:text>"
        ),
        NUMERIC_STYLES,
    ),
    "tables-negative": (
        (
            '<office:text><table:table table:name="Intent">'
            '<table:table-column table:number-columns-repeated="2"/>'
            "<table:table-row><table:table-cell><text:p>Topic</text:p></table:table-cell>"
            "<table:table-cell><text:p>Details</text:p></table:table-cell></table:table-row>"
            "<table:table-row><table:table-cell><text:p>Fruit</text:p></table:table-cell>"
            "<table:table-cell><text:p>Apples</text:p></table:table-cell>"
            "</table:table-row></table:table></office:text>"
        ),
        "",
    ),
    "language-positive": (
        (
            '<office:text><text:p text:style-name="English">English wording. '
            '<text:span text:style-name="French">Bonjour.</text:span></text:p></office:text>'
        ),
        (
            '<style:style style:name="English" style:family="paragraph">'
            '<style:text-properties fo:language="en" fo:country="GB" '
            'style:language-asian="ja" style:language-complex="ar"/></style:style>'
            '<style:style style:name="French" style:family="text">'
            '<style:text-properties fo:language="fr" fo:country="FR"/></style:style>'
        ),
    ),
    "language-negative": (
        '<office:text><text:p text:style-name="Unknown">Bonjour.</text:p></office:text>',
        (
            '<style:style style:name="Unknown" style:family="paragraph">'
            '<style:text-properties fo:language="none" fo:country="none" '
            'style:language-asian="none" style:language-complex="none"/></style:style>'
        ),
    ),
    "references-positive": (
        (
            '<office:text><text:p><text:bookmark text:name="fruit"/>Fruit destination.</text:p>'
            '<text:p><text:a xlink:href="#fruit">Visit fruit</text:a> '
            '<text:note text:id="fruit-note" text:note-class="footnote">'
            "<text:note-citation>1</text:note-citation><text:note-body>"
            "<text:p>Fruit grows on trees.</text:p></text:note-body></text:note></text:p>"
            "</office:text>"
        ),
        "",
    ),
    "references-negative": (
        (
            '<office:text><text:p><text:a xlink:href="#missing">Visit fruit</text:a>'
            "</text:p></office:text>"
        ),
        "",
    ),
    "lists-positive": (
        (
            '<office:text><text:list text:style-name="FruitList" xml:id="fruit-first">'
            "<text:list-item><text:p>Apples</text:p><text:list>"
            "<text:list-item><text:p>Red apples</text:p>"
            "</text:list-item></text:list></text:list-item><text:list-item><text:p>Pears</text:p>"
            "</text:list-item></text:list><text:p>Another list follows.</text:p>"
            '<text:list text:style-name="FruitList" text:continue-list="fruit-first">'
            "<text:list-item><text:p>Plums</text:p></text:list-item></text:list></office:text>"
        ),
        LIST_STYLE,
    ),
    "lists-negative": (
        "<office:text><text:p>1. Apples</text:p><text:p>2. Pears</text:p></office:text>",
        "",
    ),
}


def main() -> int:
    """Save selected fixtures through real Writer and record native provenance.

    Returns
    -------
    int
        Zero after successful authoring.

    Raises
    ------
    RuntimeError
        Writer did not produce the fixture.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", choices=sorted({name.split("-")[0] for name in CASES}))
    args = parser.parse_args()
    executable = find_soffice(None)
    (ROOT / "sources").mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "manifest.json"
    manifest: dict[str, Any] = (
        json.loads(manifest_path.read_text())
        if manifest_path.exists()
        else {"producer": identify_soffice(executable).version, "documents": {}}
    )
    documents: dict[str, object] = manifest["documents"]
    for name, (body, styles) in CASES.items():
        if not name.startswith(args.feature + "-"):
            continue
        with tempfile.TemporaryDirectory(prefix="odfa11y-author-text-") as temp:
            work = Path(temp)
            source = make_flat(work, "text", Variant(body=body, automatic_styles=styles))
            authored_source = ROOT / "sources" / (name + ".fodt")
            shutil.copyfile(source, authored_source)
            result = run_bounded(
                [
                    executable,
                    f"-env:UserInstallation={(work / 'profile').as_uri()}",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nolockcheck",
                    "--nofirststartwizard",
                    "--convert-to",
                    "odt:writer8",
                    "--outdir",
                    str(work / "output"),
                    str(source),
                ],
                timeout=120,
            )
            output = work / "output" / (source.stem + ".odt")
            if result.returncode or not output.is_file():
                message = "Writer did not author the selected structure fixture."
                raise RuntimeError(message)
            target = ROOT / (name + ".odt")
            shutil.copyfile(output, target)
            documents[target.name] = {
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "source_sha256": hashlib.sha256(authored_source.read_bytes()).hexdigest(),
                "schema_violations": validate(OdfDocument.open(target)).count,
            }
            sys.stdout.write(target.name + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
