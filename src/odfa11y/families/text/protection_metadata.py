# SPDX-License-Identifier: MPL-2.0
"""Normalize only explicitly requested metadata/version fields in protected XML."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import NS, qn

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.adapter import Operation

LANGUAGE_ATTRIBUTES = frozenset(
    [qn("fo", name) for name in ("language", "country", "script")]
    + [
        qn("style", name)
        for name in (
            "rfc-language-tag",
            "rfc-language-tag-asian",
            "rfc-language-tag-complex",
            "language-asian",
            "country-asian",
            "script-asian",
            "language-complex",
            "country-complex",
            "script-complex",
        )
    ]
)


def normalize_metadata(
    root: etree._Element, operation: Operation, *, creating_metadata: bool
) -> None:
    """Normalize supported metadata effects without masking unrelated styles."""
    if (
        operation.name == "set_odf_version"
        and type(operation).__module__ == "odfa11y.remediation.version"
    ):
        _version(root)
    if (
        operation.name != "set_metadata"
        or type(operation).__module__ != "odfa11y.remediation.metadata"
    ):
        return
    if creating_metadata:
        _metadata_entry(root)
    parameters = operation.as_dict()
    fields = {
        qn("dc", key)
        for key in ("title", "description", "language")
        if parameters.get(key) is not None
    }
    for meta in root.findall("office:meta", NS):
        for tag in fields:
            node = meta.find(tag)
            if node is not None:
                meta.remove(node)
        if not len(meta) and not meta.attrib and (parent := meta.getparent()) is not None:
            parent.remove(meta)
    if parameters.get("language") is not None:
        _language_defaults(root)


def _version(root: etree._Element) -> None:
    root.attrib.pop(qn("office", "version"), None)
    if root.tag == qn("manifest", "manifest"):
        root.attrib.pop(qn("manifest", "version"), None)
        for entry in root.findall("manifest:file-entry", NS):
            if entry.get(qn("manifest", "full-path")) == "/":
                entry.attrib.pop(qn("manifest", "version"), None)


def _language_defaults(root: etree._Element) -> None:
    for default in root.findall("office:styles/style:default-style", NS):
        if default.get(qn("style", "family")) != "paragraph":
            continue
        _default_properties(default)
    for styles in root.findall("office:styles", NS):
        if not len(styles) and not styles.attrib and (parent := styles.getparent()) is not None:
            parent.remove(styles)


def _metadata_entry(root: etree._Element) -> None:
    if root.tag != qn("manifest", "manifest"):
        return
    for entry in list(root):
        if (
            entry.tag == qn("manifest", "file-entry")
            and dict(entry.attrib)
            == {qn("manifest", "full-path"): "meta.xml", qn("manifest", "media-type"): "text/xml"}
            and not len(entry)
        ):
            root.remove(entry)


def _default_properties(default: etree._Element) -> None:
    for props in list(default.findall("style:text-properties", NS)):
        for attr in list(props.attrib):
            if attr in LANGUAGE_ATTRIBUTES:
                props.attrib.pop(attr)
        if not props.attrib and not len(props):
            default.remove(props)
    if (
        len(default) == 0
        and dict(default.attrib) == {qn("style", "family"): "paragraph"}
        and (parent := default.getparent()) is not None
    ):
        parent.remove(default)
