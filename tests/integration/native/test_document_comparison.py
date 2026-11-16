# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for document comparison."""

from pathlib import Path
lazy from collections.abc import Callable

from odfa11y.application.compare import is_pdf
from odfa11y.application.export import export_document
from odfa11y.application.tools import Tools
from tests.fixtures.writer import make_minimal_odt


def test_guarded_core_export_with_real_libreoffice(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    destination = tmp_path / "out.pdf"
    exported = export_document(
        source, destination, Tools(soffice=external_tool("soffice", "libreoffice"))
    )
    assert exported == destination
    assert is_pdf(exported)
    assert source.read_bytes() == before
