# SPDX-License-Identifier: MPL-2.0
"""LibreOffice export against the built-in inspector and against real veraPDF."""

lazy from pathlib import Path

import pytest

from odfa11y.errors import OutputOccupied, ToolUnavailable
from odfa11y.native.export import ExportSettings, export_pdfua, require_supported_version
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.writer import make_minimal_odt

WRITER = "writer_pdf_Export"
LINK_DESCRIPTION_RULES = {("7.18.1", "2"), ("7.18.5", "2")}


RICH_BODY = (
    b'<text:h text:outline-level="1" text:style-name="Heading1">Items</text:h>'
    b'<text:list><text:list-item><text:p text:style-name="Body">First</text:p></text:list-item>'
    b'<text:list-item><text:p text:style-name="Body">Second</text:p></text:list-item></text:list>'
    b'<text:p text:style-name="Body">See <text:a xlink:type="simple" '
    b'xlink:href="https://example.test/a">the site</text:a>.</text:p>'
)


def test_export_to_the_source_path_is_refused(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    with pytest.raises(OutputOccupied):
        export_pdfua(source, source, ExportSettings(WRITER))


def test_export_without_libreoffice_is_a_not_found_error(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    with pytest.raises(ToolUnavailable):
        export_pdfua(
            source, tmp_path / "out.pdf", ExportSettings(WRITER, soffice=tmp_path / "absent")
        )


@pytest.mark.parametrize("version", ["24.2.7.2", "26.7.9", "unknown"])
def test_unsupported_runtime_versions_are_refused(version: str) -> None:
    with pytest.raises(ToolUnavailable, match=r"install LibreOffice 26\.8 or newer"):
        require_supported_version(ToolIdentity("LibreOffice", version))


@pytest.mark.parametrize("version", ["26.8", "26.8.0.3", "27.0.0"])
def test_current_runtime_versions_are_accepted(version: str) -> None:
    require_supported_version(ToolIdentity("LibreOffice", version))
