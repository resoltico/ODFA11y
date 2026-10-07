# SPDX-License-Identifier: MPL-2.0
"""Spacing for ODF accessibility workflows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.odf import OdtPackage, StyleCatalog, qn, select_elements, visible_text_snapshot

from .models import RemediationResult

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lxml import etree


def normalize_paragraph_spacing(
    source: str | Path,
    destination: str | Path,
    *,
    reference_text: str,
    target_styles: Iterable[str],
    contains: bool = True,
    include_headings: bool = False,
) -> RemediationResult:
    """Copy effective spacing to selected styles while preserving text.

    Returns
    -------
    RemediationResult
        The saved paths and the applied spacing change.

    Raises
    ------
    ValueError
        The reference or target is missing, spacing is absent, or visible text changes.

    """
    source = Path(source)
    destination = Path(destination)
    package = OdtPackage(source)
    before_text = visible_text_snapshot(package)
    catalog = StyleCatalog(package)
    tree = catalog.content_tree

    reference = _find_reference_block(tree, reference_text, contains=contains)
    if reference is None:
        msg = f"Reference paragraph/heading not found: {reference_text!r}"
        raise ValueError(msg)
    reference_style = reference.get(qn("text", "style-name"))
    spacing = catalog.spacing_signature(reference_style)
    if not spacing:
        msg = (
            f"Reference style {reference_style!r} has no "
            f"explicit/effective spacing properties to copy."
        )
        raise ValueError(msg)

    target_styles_set = set(target_styles)
    xpath = "//text:p" + (" | //text:h" if include_headings else "")
    targets = [
        node
        for node in select_elements(tree, xpath)
        if (node.get(qn("text", "style-name")) or "(none)") in target_styles_set
    ]
    if not targets:
        msg = "No target paragraphs matched the requested style names."
        raise ValueError(msg)

    by_style = _apply_spacing(catalog, targets, spacing)

    catalog.commit_content()
    if before_text != visible_text_snapshot(package):
        msg = "Visible text changed while normalizing paragraph spacing; aborting."
        raise ValueError(msg)
    package.save(destination)
    return RemediationResult(
        source=source,
        destination=destination,
        changes=[
            (
                f"Normalized spacing for {len(targets)} paragraph(s) across "
                f"{len(by_style)} style(s) "
                f"to match reference style {reference_style!r}."
            )
        ],
    )


def _find_reference_block(
    tree: etree._ElementTree, text: str, *, contains: bool
) -> etree._Element | None:
    for node in select_elements(tree, "//text:p | //text:h"):
        current = "".join(node.itertext()).strip()
        if (contains and text in current) or (not contains and text == current):
            return node
    return None


def _unique_style_name(catalog: StyleCatalog, base: str) -> str:
    candidate = base
    counter = 1
    while catalog.style("paragraph", candidate) is not None:
        counter += 1
        candidate = f"{base}_{counter}"
    return candidate


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return value[:48] or "Body"


def _apply_spacing(
    catalog: StyleCatalog, targets: list[etree._Element], spacing: dict[str, str]
) -> dict[str, str]:
    by_style: dict[str, str] = {}
    for node in targets:
        base = node.get(qn("text", "style-name"))
        key = base or "(none)"
        if key not in by_style:
            new_name = _unique_style_name(catalog, f"A11ySpacing_{_safe_name(key)}")
            catalog.clone_paragraph_style_with_spacing(
                base_style_name=base,
                new_style_name=new_name,
                spacing=spacing,
            )
            by_style[key] = new_name
        node.set(qn("text", "style-name"), by_style[key])

    return by_style
