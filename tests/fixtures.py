# SPDX-License-Identifier: MPL-2.0
"""Build synthetic ODT documents with selected structural features."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from pathlib import Path


TEXT_MEDIA_TYPE = "application/vnd.oasis.opendocument.text"


class Features(TypedDict, total=False):
    """Independent structural features of the synthetic document."""

    with_plain_email: bool
    with_data_table: bool
    with_table_header: bool
    with_image_without_alt: bool
    add_blank_body_paragraph: bool


def make_minimal_odt(
    path: Path,
    *,
    version: str = "1.4",
    title: str = "Synthetic accessible document",
    language: str = "en-GB",
    with_plain_email: bool = False,
    with_data_table: bool = False,
    with_table_header: bool = False,
    with_image_without_alt: bool = False,
    add_blank_body_paragraph: bool = False,
) -> Path:
    """Create a synthetic Writer document with selected structural features.

    Returns
    -------
    Path
        The created fixture path.

    """
    plain_email = (
        "Contact test@example.com for information." if with_plain_email else "Body paragraph."
    )
    blank = '<text:p text:style-name="Body"/>' if add_blank_body_paragraph else ""
    table = ""
    if with_data_table:
        row1 = """
        <table:table-row>
          <table:table-cell><text:p>Item</text:p></table:table-cell>
          <table:table-cell><text:p>Amount</text:p></table:table-cell>
        </table:table-row>"""
        row2 = """
        <table:table-row>
          <table:table-cell><text:p>A</text:p></table:table-cell>
          <table:table-cell><text:p>10</text:p></table:table-cell>
        </table:table-row>"""
        row3 = """
        <table:table-row>
          <table:table-cell><text:p>B</text:p></table:table-cell>
          <table:table-cell><text:p>20</text:p></table:table-cell>
        </table:table-row>"""
        columns = "<table:table-column/><table:table-column/>"
        if with_table_header:
            rows = f"{columns}<table:table-header-rows>{row1}</table:table-header-rows>{row2}{row3}"
        else:
            rows = columns + row1 + row2 + row3
        table = f'<table:table table:name="Data">{rows}</table:table>'

    frame = ""
    manifest_picture = ""
    picture_member: tuple[str, bytes] | None = None
    if with_image_without_alt:
        frame = """
        <draw:frame draw:name="Logo" text:anchor-type="paragraph" svg:width="1cm" svg:height="1cm">
          <draw:image xlink:href="Pictures/logo.svg" xlink:type="simple"
          xlink:show="embed" xlink:actuate="onLoad"/>
        </draw:frame>
        """
        manifest_picture = (
            '<manifest:file-entry manifest:full-path="Pictures/logo.svg" '
            'manifest:media-type="image/svg+xml"/>'
        )
        picture_member = (
            "Pictures/logo.svg",
            (
                b'<svg xmlns="http://www.w3.org/2000/svg" width="10" '
                b'height="10"><rect width="10" height="10"/></svg>'
            ),
        )

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 office:version="{version}">
 <office:font-face-decls/>
 <office:automatic-styles/>
 <office:body><office:text>
   <text:h text:outline-level="1" text:style-name="Heading1">Synthetic heading</text:h>
   <text:p text:style-name="Body">{plain_email}</text:p>
   {blank}
   {table}
   <text:p text:style-name="Body">{frame}</text:p>
 </office:text></office:body>
</office:document-content>"""

    styles = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="{version}">
 <office:styles>
   <style:default-style style:family="paragraph">
     <style:text-properties fo:language="{language.split("-", 1)[0]}"
     fo:country="{language.split("-", 1)[1]}"/>
   </style:default-style>
   <style:style style:name="Body" style:family="paragraph">
     <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.2cm"
     fo:line-height="115%"/>
   </style:style>
   <style:style style:name="BodyTight" style:family="paragraph">
     <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0cm" fo:line-height="100%"/>
   </style:style>
   <style:style style:name="Heading1" style:family="paragraph" style:default-outline-level="1">
     <style:paragraph-properties fo:margin-top="0.3cm" fo:margin-bottom="0.2cm"/>
   </style:style>
 </office:styles>
 <office:automatic-styles/>
 <office:master-styles/>
</office:document-styles>"""

    meta = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 office:version="{version}">
 <office:meta><dc:title>{title}</dc:title><dc:language>{language}</dc:language></office:meta>
</office:document-meta>"""

    manifest = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest
xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="{version}">
 <manifest:file-entry manifest:full-path="/" manifest:version="{version}"
 manifest:media-type="application/vnd.oasis.opendocument.text"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
 {manifest_picture}
</manifest:manifest>"""

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "mimetype", "application/vnd.oasis.opendocument.text", compress_type=zipfile.ZIP_STORED
        )
        zf.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("styles.xml", styles, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("meta.xml", meta, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        if picture_member:
            zf.writestr(picture_member[0], picture_member[1], compress_type=zipfile.ZIP_DEFLATED)
    return path
