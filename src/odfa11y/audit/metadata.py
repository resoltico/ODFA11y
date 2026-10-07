# SPDX-License-Identifier: MPL-2.0
"""Audit document title and language metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import NS, qn, select_elements
from odfa11y.report import rules

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.report import Report


def audit_metadata(
    meta_tree: etree._ElementTree, styles_tree: etree._ElementTree, report: Report
) -> None:
    """Report missing or empty document title and language metadata."""
    title = meta_tree.findtext(".//dc:title", namespaces=NS)
    if not title or not title.strip():
        report.add(rules.META001, "Document title metadata is missing.", location="meta.xml")
    else:
        report.metadata["title"] = title.strip()

    language = meta_tree.findtext(".//dc:language", namespaces=NS)
    default_language = _default_style_language(styles_tree)
    if not (language and language.strip()) and not default_language:
        report.add(
            rules.META002,
            "Document language is not declared in metadata or the default paragraph style.",
            location="meta.xml/styles.xml",
        )
        return
    report.metadata["language"] = (language or default_language or "").strip()
    if (
        language
        and default_language
        and _normalize_lang(language) != _normalize_lang(default_language)
    ):
        report.add(
            rules.META003,
            location="meta.xml/styles.xml",
            details={"metadata": language, "default_style": default_language},
        )


def _default_style_language(styles_tree: etree._ElementTree) -> str | None:
    nodes = select_elements(
        styles_tree, "//style:default-style[@style:family='paragraph']/style:text-properties"
    )
    if not nodes:
        return None
    props = nodes[0]
    language = props.get(qn("fo", "language"))
    country = props.get(qn("fo", "country"))
    if language and country and country.lower() != "none":
        return f"{language}-{country}"
    return language


def _normalize_lang(value: str) -> str:
    return value.replace("_", "-").lower()
