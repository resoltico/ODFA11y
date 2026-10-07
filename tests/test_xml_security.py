# SPDX-License-Identifier: MPL-2.0
"""Exercise XML external-entity protection using actual package members."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import PackageStorage

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def test_external_file_entity_is_not_expanded(tmp_path: Path) -> None:
    private = tmp_path / "private.txt"
    private.write_text("PRIVATE_ENTITY_SAMPLE", encoding="utf-8")
    source = make_minimal_odt(tmp_path / "source.odt")
    package = PackageStorage(source)
    payload = package.read("content.xml")
    declaration = f'<!DOCTYPE office:document-content [<!ENTITY leak SYSTEM "{private.as_uri()}">]>'
    payload = payload.replace(b"?>", b"?>" + declaration.encode(), 1)
    payload = payload.replace(b"Body paragraph.", b"&leak;")
    package.write_member("content.xml", payload)
    package.save(source)
    parsed = PackageStorage(source).parse_xml("content.xml")
    text = "".join(parsed.getroot().itertext())
    assert "PRIVATE_ENTITY_SAMPLE" not in text
    assert "&leak;" in text
