# SPDX-License-Identifier: MPL-2.0
"""Native implicit Writer placement cannot be replaced by an unproven graphic style."""

from collections.abc import Callable
lazy from pathlib import Path

from odfa11y.concepts import graphics_fingerprint
from odfa11y.decisions.edit import Status
from odfa11y.native.export import ExportSettings, export_pdfua
from odfa11y.odf import NS, OdfDocument, Part, qn, validate
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.plans.fidelity import Pagination
from tests.fixtures.answers import graphic_answer, graphic_inputs
from tests.fixtures.native_resources import PIXELS, decoded_images, writer_resource
from tests.fixtures.operations import apply_answers, assert_refused
lazy from tests.fixtures.answers import apply_in_memory


def test_unstyled_native_role_refusal_preserves_original_placement_and_publication(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    document = OdfDocument.open(writer_resource(tmp_path))
    frame = document.tree(Part.CONTENT).find(".//draw:frame", NS)
    assert frame is not None
    assert frame.get(qn("draw", "style-name")) is None
    for node in list(frame):
        if node.tag in {qn("svg", "title"), qn("svg", "desc")}:
            frame.remove(node)
    source = document.save(tmp_path / "unstyled.fodt")
    assert validate(document).count == 0
    operation = graphic_inputs({
        "Asset": graphic_answer(
            decorative=True, fingerprint=graphics_fingerprint(document, [frame])
        )
    })
    before = document.checkpoint()
    outcome = apply_in_memory(document, operation)[0]
    assert outcome.status == Status.FAILED
    assert "placement and wrapping are unestablished" in outcome.message
    assert not document.changed_since(before)
    destination = tmp_path / "destination.fodt"
    destination.write_bytes(b"Existing destination")
    original = source.read_bytes()
    assert_refused(
        apply_answers(source, destination, [operation]),
        match="placement and wrapping are unestablished",
    )
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"Existing destination"
    unchanged = document.save(tmp_path / "unchanged.fodt")
    assert unchanged.read_bytes() == original
    settings = ExportSettings("writer_pdf_Export", external_tool("soffice", "libreoffice"))
    baseline = export_pdfua(source, tmp_path / "baseline.pdf", settings)
    actual = export_pdfua(unchanged, tmp_path / "unchanged.pdf", settings)
    assert ((4, 4), PIXELS) in decoded_images(baseline)
    assert decoded_images(actual) == decoded_images(baseline)
    assert compare_pdfs(baseline, actual, Pagination.SAME(raster_tolerance=0.0)).error_count == 0
