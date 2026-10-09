# SPDX-License-Identifier: MPL-2.0
"""Effective URI destinations, independent expected references and malformed contexts."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject

from odfa11y.errors import ToolFailedError
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.fidelity.snapshot import read_snapshot

from .pdf_fixtures import register, text_pdf

if TYPE_CHECKING:
    from pathlib import Path

    from pypdf.generic import PdfObject


def _with_base(path: Path, links: list[str], base: PdfObject | None) -> Path:
    text_pdf(path, [["Identical text"]], links=links)
    writer = PdfWriter(clone_from=path)
    if base is not None:
        writer.root_object[NameObject("/URI")] = register(
            writer,
            DictionaryObject({
                NameObject("/Base"): register(writer, base),
            }),
        )
    writer.write(path)
    return path


def test_base_change_and_equivalent_absolute_destinations(tmp_path: Path) -> None:
    left = _with_base(
        tmp_path / "left.pdf", ["file.pdf"] * 2, TextStringObject("https://example.test/one/")
    )
    right = _with_base(
        tmp_path / "right.pdf", ["file.pdf"] * 2, TextStringObject("https://example.test/two/")
    )
    report = compare_pdfs(left, right, FidelityPolicy())
    assert {f.rule_id for f in report.findings} == {"FID004", "FID006"}
    absolute = _with_base(
        tmp_path / "absolute.pdf",
        ["https://example.test/one/file.pdf"] * 2,
        TextStringObject("https://irrelevant.test/"),
    )
    assert compare_pdfs(left, absolute, FidelityPolicy()).findings == []
    assert read_snapshot(left).links == Counter({"https://example.test/one/file.pdf": 2})


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("../g", "https://example.test/a/g"),
        ("g//h", "https://example.test/a/b/g//h"),
        ("./g", "https://example.test/a/b/g"),
        ("g/./h", "https://example.test/a/b/g/h"),
        ("g/../h", "https://example.test/a/b/h"),
        ("g/.", "https://example.test/a/b/g/"),
        ("g/..", "https://example.test/a/b/"),
        ("../../../../g", "https://example.test/g"),
        ("%2E%2E/g", "https://example.test/a/b/%2E%2E/g"),
        ("g?y/../z#s/./t", "https://example.test/a/b/g?y/../z#s/./t"),
        ("/g", "https://example.test/g"),
        ("//other.test/g", "https://other.test/g"),
        ("?y", "https://example.test/a/b/c?y"),
        ("#s", "https://example.test/a/b/c?q#s"),
        ("", "https://example.test/a/b/c?q"),
        ("?", "https://example.test/a/b/c?"),
        ("?#", "https://example.test/a/b/c?#"),
        ("g?y#s", "https://example.test/a/b/g?y#s"),
        ("g%2Fh", "https://example.test/a/b/g%2Fh"),
        ("mailto:a@example.test", "mailto:a@example.test"),
    ],
)
def test_reference_resolution_from_written_pdf(
    tmp_path: Path, reference: str, expected: str
) -> None:
    path = _with_base(
        tmp_path / "reference.pdf", [reference], TextStringObject("https://example.test/a/b/c?q")
    )
    assert read_snapshot(path).links == Counter({expected: 1})


@pytest.mark.parametrize(
    "base",
    [
        None,
        TextStringObject("relative/"),
        TextStringObject("mailto:a@example.test"),
        TextStringObject("https://host/%ZZ"),
        NumberObject(1),
    ],
)
def test_unestablished_or_malformed_base_refuses(tmp_path: Path, base: PdfObject | None) -> None:
    path = _with_base(tmp_path / "bad.pdf", ["file.pdf"], base)
    with pytest.raises(ToolFailedError, match=r"(Base|relative|Relative)"):
        read_snapshot(path)


@pytest.mark.parametrize("uri", ["https://host/%ZZ", "https://host/a b", "https://[bad/", ":bad"])
def test_malformed_action_refuses(tmp_path: Path, uri: str) -> None:
    path = _with_base(tmp_path / "bad.pdf", [uri], TextStringObject("https://example.test/"))
    with pytest.raises(ToolFailedError, match="URI"):
        read_snapshot(path)


def test_file_base_and_empty_authority_reference(tmp_path: Path) -> None:
    path = _with_base(tmp_path / "file.pdf", ["../g", "///g"], TextStringObject("file:///a/b/c"))
    assert read_snapshot(path).links == Counter({"file:///a/g": 1, "file:///g": 1})


@pytest.mark.parametrize("shape", ["catalog", "subtype", "missing-uri", "uri-name"])
def test_malformed_catalog_and_action_values_refuse(tmp_path: Path, shape: str) -> None:
    path = _with_base(tmp_path / "shape.pdf", ["https://example.test/"], None)
    writer = PdfWriter(clone_from=path)
    if shape == "catalog":
        writer.root_object[NameObject("/URI")] = NumberObject(1)
    else:
        annotations = writer.pages[0]["/Annots"].get_object()
        assert isinstance(annotations, ArrayObject)
        annotation = annotations[0].get_object()
        assert isinstance(annotation, DictionaryObject)
        action = annotation["/A"].get_object()
        assert isinstance(action, DictionaryObject)
        if shape == "subtype":
            action[NameObject("/S")] = NumberObject(1)
        elif shape == "missing-uri":
            del action["/URI"]
        else:
            action[NameObject("/URI")] = NameObject("/invalid")
    writer.write(path)
    with pytest.raises(ToolFailedError, match="Expected"):
        read_snapshot(path)
