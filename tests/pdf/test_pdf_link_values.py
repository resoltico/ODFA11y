# SPDX-License-Identifier: MPL-2.0
"""Real parser objects exercise fidelity's annotation boundary."""

lazy from pathlib import Path

import pytest
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NullObject,
    NumberObject,
    TextStringObject,
)

from odfa11y.cli import main
from odfa11y.errors import ToolFailure
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.pdf.fidelity.snapshot import read_snapshot
from odfa11y.plans.fidelity import Pagination
from tests.fixtures.pdf import register, tagged_writer


@pytest.mark.parametrize("shape", ["array", "item", "action"])
def test_malformed_annotations_fail_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], shape: str
) -> None:
    writer = tagged_writer(["H1"])
    values = {
        "array": NumberObject(7),
        "item": ArrayObject([NullObject()]),
        "action": ArrayObject([
            DictionaryObject({
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/A"): NumberObject(7),
            })
        ]),
    }
    writer.pages[0][NameObject("/Annots")] = values[shape]
    path = tmp_path / "malformed.pdf"
    writer.write(path)
    with pytest.raises(ToolFailure, match="Expected a PDF"):
        read_snapshot(path)
    assert main(["compare", str(path), str(path)]) == 3
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("indirect", [False, True])
def test_uri_multiplicity_and_change(tmp_path: Path, *, indirect: bool) -> None:
    paths = []
    for target in ["old", "new"]:
        writer = tagged_writer(["H1"])
        uri = TextStringObject(f"https://example.test/{target}")
        value = register(writer, uri) if indirect else uri
        annotation = DictionaryObject({
            NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/A"): DictionaryObject({
                NameObject("/S"): NameObject("/URI"),
                NameObject("/URI"): value,
            }),
        })
        writer.pages[0][NameObject("/Annots")] = ArrayObject([annotation, annotation])
        path = tmp_path / f"{target}.pdf"
        writer.write(path)
        assert read_snapshot(path).links[f"https://example.test/{target}"] == 2
        paths.append(path)
    report = compare_pdfs(paths[0], paths[1], Pagination.SAME())
    assert report.error_count != 0
    assert any(f.rule_id.startswith("FID") for f in report.findings)
