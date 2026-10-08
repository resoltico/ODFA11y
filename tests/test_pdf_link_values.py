# SPDX-License-Identifier: MPL-2.0
"""Real parser objects exercise fidelity's annotation boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from odfa11y.errors import ToolFailedError
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.fidelity.snapshot import read_snapshot

from .pdf_fixtures import register, tagged_writer

if TYPE_CHECKING:
    from pathlib import Path


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
    with pytest.raises(ToolFailedError, match="Expected a PDF"):
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
            NameObject("/A"): DictionaryObject({NameObject("/URI"): value}),
        })
        writer.pages[0][NameObject("/Annots")] = ArrayObject([annotation, annotation])
        path = tmp_path / f"{target}.pdf"
        writer.write(path)
        assert read_snapshot(path).links[f"https://example.test/{target}"] == 2
        paths.append(path)
    report = compare_pdfs(paths[0], paths[1], FidelityPolicy())
    assert not report.passed
    assert any(f.rule_id.startswith("FID") for f in report.findings)
