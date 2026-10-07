# SPDX-License-Identifier: MPL-2.0
"""Build minimal synthetic ODF documents of every kind, as packages or flat XML files."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

OASIS = "application/vnd.oasis.opendocument."
NAMESPACES = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:db="urn:oasis:names:tc:opendocument:xmlns:database:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"'
)
TABLE_BODY = (
    '<table:table table:name="Sheet1"><table:table-column/>'
    '<table:table-row><table:table-cell office:value-type="string">'
    "<text:p>Cell</text:p></table:table-cell></table:table-row></table:table>"
)


@dataclass(frozen=True, slots=True)
class KindSpec:
    """A document kind as a test builds it."""

    name: str
    media_type: str
    extension: str
    body: str
    family: str
    schema_valid: bool = True
    master: bool = False


KIND_SPECS = {
    spec.name: spec
    for spec in (
        KindSpec(
            "text",
            OASIS + "text",
            ".odt",
            "<office:text><text:p>Body text.</text:p></office:text>",
            "text",
        ),
        KindSpec(
            "text-template",
            OASIS + "text-template",
            ".ott",
            "<office:text><text:p>Body text.</text:p></office:text>",
            "text",
        ),
        KindSpec(
            "spreadsheet",
            OASIS + "spreadsheet",
            ".ods",
            f"<office:spreadsheet>{TABLE_BODY}</office:spreadsheet>",
            "spreadsheet",
        ),
        KindSpec(
            "spreadsheet-template",
            OASIS + "spreadsheet-template",
            ".ots",
            f"<office:spreadsheet>{TABLE_BODY}</office:spreadsheet>",
            "spreadsheet",
        ),
        KindSpec(
            "graphics",
            OASIS + "graphics",
            ".odg",
            '<office:drawing><draw:page draw:name="page1" draw:master-page-name="Default"/>'
            "</office:drawing>",
            "graphics",
            master=True,
        ),
        KindSpec(
            "presentation",
            OASIS + "presentation",
            ".odp",
            '<office:presentation><draw:page draw:name="page1" draw:master-page-name="Default"/>'
            "</office:presentation>",
            "presentation",
            master=True,
        ),
        KindSpec(
            "image",
            OASIS + "image",
            ".odi",
            '<office:image><draw:frame draw:name="Picture"><draw:image>'
            "<office:binary-data>"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
            "</office:binary-data></draw:image>"
            "<svg:title>Synthetic graphic</svg:title></draw:frame></office:image>",
            "image",
        ),
        KindSpec(
            "database",
            OASIS + "base",
            ".odb",
            "<office:database><db:data-source><db:connection-data>"
            '<db:connection-resource xlink:type="simple" '
            'xlink:href="sdbc:postgresql:example.invalid"/>'
            "</db:connection-data></db:data-source></office:database>",
            "database",
        ),
    )
}


def _meta(version: str) -> str:
    return (
        f'<office:document-meta {NAMESPACES} office:version="{version}"><office:meta>'
        "<dc:title>Synthetic document</dc:title><dc:language>en-GB</dc:language>"
        "</office:meta></office:document-meta>"
    )


def _automatic_styles(styles: str) -> str:
    return f"<office:automatic-styles>{styles}</office:automatic-styles>" if styles else ""


def _content(spec: KindSpec, version: str, automatic_styles: str) -> str:
    return (
        f'<office:document-content {NAMESPACES} office:version="{version}">'
        f"{_automatic_styles(automatic_styles)}"
        f"<office:body>{spec.body}</office:body></office:document-content>"
    )


MASTER_STYLES = (
    '<office:automatic-styles><style:page-layout style:name="PM1"/></office:automatic-styles>'
    '<office:master-styles><style:master-page style:name="Default" '
    'style:page-layout-name="PM1"/></office:master-styles>'
)


def _styles(spec: KindSpec, version: str) -> str:
    inner = MASTER_STYLES if spec.master else ""
    return (
        f'<office:document-styles {NAMESPACES} office:version="{version}">{inner}'
        "</office:document-styles>"
    )


def _manifest(version: str, media_type: str) -> str:
    return (
        f'<manifest:manifest {NAMESPACES} manifest:version="{version}">'
        f'<manifest:file-entry manifest:full-path="/" manifest:version="{version}" '
        f'manifest:media-type="{media_type}"/></manifest:manifest>'
    )


@dataclass(frozen=True, slots=True)
class Variant:
    """How a synthetic document departs from a well-formed one of its kind."""

    version: str = "1.4"
    media_type: str | None = None
    manifest_media_type: str | None = None
    body: str | None = None
    extension: str | None = None
    mimetype: bool = True
    automatic_styles: str = ""


WELL_FORMED = Variant()


def make_package(directory: Path, kind: str, variant: Variant = WELL_FORMED) -> Path:
    """Write a minimal ZIP package of a kind.

    Returns
    -------
    Path
        The file path.

    """
    spec = KIND_SPECS[kind]
    media = variant.media_type or spec.media_type
    path = directory / f"synthetic-{kind}{variant.extension or spec.extension}"
    shaped = KindSpec(spec.name, media, spec.extension, variant.body or spec.body, spec.family)
    with zipfile.ZipFile(path, "w") as archive:
        if variant.mimetype:
            archive.writestr("mimetype", media, compress_type=zipfile.ZIP_STORED)
        archive.writestr("content.xml", _content(shaped, variant.version, variant.automatic_styles))
        archive.writestr("styles.xml", _styles(spec, variant.version))
        archive.writestr("meta.xml", _meta(variant.version))
        archive.writestr(
            "META-INF/manifest.xml",
            _manifest(variant.version, variant.manifest_media_type or media),
        )
    return path


def make_flat(directory: Path, kind: str, variant: Variant = WELL_FORMED) -> Path:
    """Write a minimal flat XML document of a kind.

    Returns
    -------
    Path
        The file path.

    """
    spec = KIND_SPECS[kind]
    media = variant.media_type or spec.media_type
    flat_extension = variant.extension or f".f{spec.extension[1:]}"
    path = directory / f"synthetic-{kind}{flat_extension}"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document {NAMESPACES} office:version="{variant.version}" '
        f'office:mimetype="{media}">'
        "<office:meta><dc:title>Synthetic document</dc:title>"
        "<dc:language>en-GB</dc:language></office:meta>"
        f"{MASTER_STYLES if spec.master else _automatic_styles(variant.automatic_styles)}"
        f"<office:body>{variant.body or spec.body}</office:body></office:document>",
        encoding="utf-8",
    )
    return path
