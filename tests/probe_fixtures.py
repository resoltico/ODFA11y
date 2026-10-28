# SPDX-License-Identifier: MPL-2.0
"""Independent PDF controls and explicit probe doubles for native workflow tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from odfa11y.native.probes import CapabilityResult, CapabilityStatus, ProbeExecution, ProbeId

from .pdf_fixtures import (
    annotation_references,
    dictionary,
    link_elements,
    map_link,
    marked_text,
    register,
    set_page_content,
    tagged_writer,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pypdf import PdfWriter

    from odfa11y.native.export import ExportSettings
    from odfa11y.native.probes import CapabilityProbe, ProbeCache
    from odfa11y.native.process import ToolIdentity

PURPOSE = "ODFA11y reviewed link purpose."


def conclusive_probe(
    _cache: ProbeCache,
    probe: CapabilityProbe,
    identity: ToolIdentity,
    _settings: ExportSettings,
    **_options: object,
) -> ProbeExecution:
    """Keep unrelated workflow controls independent of native capability startup.

    Returns
    -------
    ProbeExecution
        An explicit supported observation with the provided identity.

    """
    return ProbeExecution(
        CapabilityResult(probe.id, probe.family, CapabilityStatus.SUPPORTED, identity)
    )


def pdf_control(probe: ProbeId, *, supported: bool) -> PdfWriter:
    """Build a PDF exhibiting or violating the exact declared experiment property.

    Returns
    -------
    PdfWriter
        An independently specified positive or negative exported-PDF control.

    """
    if probe == ProbeId.LINK_DESCRIPTIONS:
        writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
        annotation = annotation_references(writer)[0]
        map_link(writer, link_elements(writer)[0], annotation)
        if supported:
            dictionary(annotation)[NameObject("/Contents")] = TextStringObject(PURPOSE)
        else:
            dictionary(annotation).pop(NameObject("/Contents"), None)
        return writer
    if probe == ProbeId.DECORATIVE_ROLE:
        return graphic_control(artifact=supported)
    if probe in {ProbeId.WRITER_HEADER_COLUMNS, ProbeId.CALC_PDFUA}:
        header = "TH" if supported else "TD"
        return tagged_writer(["H1", ("Table", [("TR", [header, "TD"]), ("TR", [header, "TD"])])])
    writer = tagged_writer(["H1", "P"])
    if not supported:
        writer.root_object.pop(NameObject("/StructTreeRoot"), None)
        writer.root_object.pop(NameObject("/MarkInfo"), None)
    return writer


def graphic_control(*, artifact: bool) -> PdfWriter:
    """Paint two images, with independently controlled semantic/artifact structure.

    Returns
    -------
    PdfWriter
        One meaningful described Figure and the decorative or undescribed peer.

    """
    writer = tagged_writer(
        ["H1", "Figure"] if artifact else ["H1", "Figure", "Figure"],
        figure_alt="Meaningful red square",
    )
    # The negative peer must be a real undescribed Figure, rather than a dropped image.
    root = writer.root_object["/StructTreeRoot"]
    assert isinstance(root, DictionaryObject)
    if not artifact:
        children = root["/K"]
        assert isinstance(children, ArrayObject)
        peer = children[2].get_object()
        assert isinstance(peer, DictionaryObject)
        peer.pop(NameObject("/Alt"), None)
    images = DictionaryObject()
    for name, colour in [("Meaningful", b"\xff\x00\x00"), ("Decoration", b"\x00\x00\xff")]:
        image = DecodedStreamObject()
        image.set_data(colour * 4)
        image.update({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(2),
            NameObject("/Height"): NumberObject(2),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        })
        images[NameObject("/" + name)] = register(writer, image)
    peer = (
        "/Artifact BMC /Decoration Do EMC"
        if artifact
        else "/Figure <</MCID 2>> BDC /Decoration Do EMC"
    )
    set_page_content(
        writer,
        writer.pages[0],
        marked_text(0) + "\n/Figure <</MCID 1>> BDC /Meaningful Do EMC\n" + peer,
    )
    resources = writer.pages[0]["/Resources"]
    assert isinstance(resources, DictionaryObject)
    resources[NameObject("/XObject")] = images
    return writer


def fake_export(probe: ProbeId, *, supported: bool) -> Callable[[Path, Path, ExportSettings], Path]:
    """Return a deterministic exporter producing the independent PDF control.

    Returns
    -------
    Callable[[Path, Path, ExportSettings], Path]
        The controlled exporter.

    """

    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        pdf_control(probe, supported=supported).write(destination)
        return destination

    return export
