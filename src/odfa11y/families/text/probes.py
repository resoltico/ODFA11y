# SPDX-License-Identifier: MPL-2.0
"""Writer's declared link, decorative-image and header-column experiments."""

from __future__ import annotations

from functools import partial
from io import BytesIO
lazy from pathlib import Path

from PIL import Image

from odfa11y.native.probe_pdf import decorative_role, link_descriptions, writer_header_columns
from odfa11y.native.probe_sources import write_probe_package
from odfa11y.native.probes import CapabilityProbe, ProbeId
from odfa11y.odf import Family

LINK_PURPOSE = "ODFA11y reviewed link purpose."


def write_link_probe(directory: Path) -> Path:
    """Write one titled link whose purpose differs from its visible label.

    Returns
    -------
    Path
        The synthetic Writer package.

    """
    return write_probe_package(
        directory / "link.odt",
        "application/vnd.oasis.opendocument.text",
        "<office:text><text:p>Read the "
        f'<text:a office:title="{LINK_PURPOSE}" xlink:type="simple" xlink:href="https://example.com/">'
        "example link</text:a>.</text:p></office:text>",
    )


def _png(colour: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), colour).save(output, format="PNG")
    return output.getvalue()


def write_decorative_probe(directory: Path) -> Path:
    """Write a described image and a separately painted decorative peer.

    Returns
    -------
    Path
        The synthetic Writer package containing two distinct local images.

    """
    body = (
        "<office:text><text:p>Meaningful: "
        '<draw:frame draw:name="Meaningful" text:anchor-type="as-char" '
        'svg:width="1cm" svg:height="1cm">'
        '<draw:image xlink:href="Pictures/meaningful.png" xlink:type="simple"/>'
        "<svg:title>A meaningful red square.</svg:title></draw:frame>"
        ' Decorative: <draw:frame draw:name="Decorative" draw:style-name="Decorative" '
        'text:anchor-type="as-char" svg:width="1cm" svg:height="1cm">'
        '<draw:image xlink:href="Pictures/decorative.png" xlink:type="simple"/>'
        "</draw:frame></text:p></office:text>"
    )
    styles = (
        '<style:style style:name="Decorative" style:family="graphic">'
        '<style:graphic-properties draw:decorative="true"/></style:style>'
    )
    return write_probe_package(
        directory / "decorative.odt",
        "application/vnd.oasis.opendocument.text",
        body,
        automatic_styles=styles,
        assets={"Pictures/meaningful.png": _png("red"), "Pictures/decorative.png": _png("blue")},
    )


def write_header_column_probe(directory: Path) -> Path:
    """Write two row labels as semantic header columns, with no header rows.

    Returns
    -------
    Path
        The synthetic Writer table.

    """
    rows = "".join(
        "<table:table-row>"
        + "".join(
            '<table:table-cell office:value-type="string"><text:p>'
            f"{value}</text:p></table:table-cell>"
            for value in values
        )
        + "</table:table-row>"
        for values in [("Apples", "Three"), ("Pears", "Four")]
    )
    return write_probe_package(
        directory / "columns.odt",
        "application/vnd.oasis.opendocument.text",
        '<office:text><table:table table:name="Fruit">'
        "<table:table-header-columns><table:table-column/>"
        "</table:table-header-columns><table:table-column/>"
        + rows
        + "</table:table></office:text>",
    )


PROBES = (
    CapabilityProbe(
        ProbeId.LINK_DESCRIPTIONS,
        Family.TEXT,
        write_link_probe,
        "writer_pdf_Export",
        partial(link_descriptions, expected=LINK_PURPOSE),
        frozenset({"link.description", "text.linkify_addresses"}),
        "Writer retains the authored link purpose in tagged link metadata.",
    ),
    CapabilityProbe(
        ProbeId.DECORATIVE_ROLE,
        Family.TEXT,
        write_decorative_probe,
        "writer_pdf_Export",
        decorative_role,
        frozenset({"graphic.alternative"}),
        (
            "Writer paints the decorative peer as an artifact and the meaningful "
            "peer as a described Figure."
        ),
    ),
    CapabilityProbe(
        ProbeId.WRITER_HEADER_COLUMNS,
        Family.TEXT,
        write_header_column_probe,
        "writer_pdf_Export",
        writer_header_columns,
        frozenset({"table.headers"}),
        "Writer exports both semantic column-header cells as TH.",
    ),
)
