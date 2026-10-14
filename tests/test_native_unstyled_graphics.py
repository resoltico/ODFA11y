# SPDX-License-Identifier: MPL-2.0
"""Native implicit Writer placement cannot be replaced by an unproven graphic style."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.adapter import Status
from odfa11y.content import GraphicAlternative, graphics_fingerprint
from odfa11y.errors import RemediationError
from odfa11y.families.text import SetGraphicAlternatives
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.odf import NS, OdfDocument, Part, qn, validate
from odfa11y.pdf import ExportSettings, export_pdfua
from odfa11y.remediation import remediate

from .native_resource_fixtures import PIXELS, decoded_images, writer_resource

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.integration


def test_unstyled_native_role_refusal_preserves_original_placement_and_publication(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    document = OdfDocument.open(writer_resource(tmp_path))
    frame = document.edit(Part.CONTENT).find(".//draw:frame", NS)
    assert frame is not None
    assert frame.get(qn("draw", "style-name")) is None
    for node in list(frame):
        if node.tag in {qn("svg", "title"), qn("svg", "desc")}:
            frame.remove(node)
    source = document.save(tmp_path / "unstyled.fodt")
    assert validate(document).count == 0
    operation = SetGraphicAlternatives({
        "Asset": GraphicAlternative(
            decorative=True, fingerprint=graphics_fingerprint(document, [frame])
        )
    })
    before = document.edit_count
    outcome = operation.apply(document)[0]
    assert outcome.status == Status.FAILED
    assert "placement and wrapping are unestablished" in outcome.message
    assert document.edit_count == before
    destination = tmp_path / "destination.fodt"
    destination.write_bytes(b"Existing destination")
    original = source.read_bytes()
    with pytest.raises(RemediationError, match="placement and wrapping are unestablished"):
        remediate(source, destination, [operation])
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"Existing destination"
    unchanged = document.save(tmp_path / "unchanged.fodt")
    assert unchanged.read_bytes() == original
    settings = ExportSettings("writer_pdf_Export", external_tool("soffice", "libreoffice"))
    baseline = export_pdfua(source, tmp_path / "baseline.pdf", settings)
    actual = export_pdfua(unchanged, tmp_path / "unchanged.pdf", settings)
    assert ((4, 4), PIXELS) in decoded_images(baseline)
    assert decoded_images(actual) == decoded_images(baseline)
    assert compare_pdfs(baseline, actual, FidelityPolicy(raster_tolerance=0.0)).passed
