# SPDX-License-Identifier: MPL-2.0
"""Writer-authored real lists retain list tags; typed markers remain ordinary text."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from odfa11y.pipeline.native import export_document
from odfa11y.tools import Tools
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_list_structure(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    executable = external_tool("soffice", "libreoffice")
    output = tmp_path / "lists.pdf"
    export_document(TESTS / "text_corpus" / f"lists-{case}.odt", output, Tools(soffice=executable))
    reader = PdfReader(output)
    pending = [reader.root_object["/StructTreeRoot"]]
    roles = []
    while pending:
        node = pending.pop().get_object()
        if not isinstance(node, dict):
            continue
        roles.append(str(node.get("/S", "")))
        kids = node.get("/K", [])
        pending.extend(kids if isinstance(kids, list) else [kids])
    assert ("/L" in roles) is (case == "positive")
    assert ("/LI" in roles) is (case == "positive")
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Apples" in text
    assert "Pears" in text
