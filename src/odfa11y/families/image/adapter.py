# SPDX-License-Identifier: MPL-2.0
"""Standard image source semantics with explicit unsupported native PDF export."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem, config_tables
from odfa11y.content import graphic_descriptions, protected_xml, set_style_language, style_language
from odfa11y.odf import Family, Part, qn, select_elements

from .audit import audit_image
from .operations import SetGraphicDescriptions

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.adapter import Operation
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Finding


def _parse(data: dict[str, object]) -> list[Operation]:
    config_tables.known(data, {"graphics"}, "image")
    entries = graphic_descriptions(config_tables.table(data, "graphics"), "image.graphics")
    return [SetGraphicDescriptions(entries)] if entries else []


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    return tuple(
        protected_xml(body, omitted_elements=(qn("svg", "title"), qn("svg", "desc")))
        for body in bodies
    )


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed: int) -> bool:
    return removed == 0 and before == after


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> bool:
    return set_style_language(document, tag, "paragraph")


def _template(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    lines = []
    for finding in by_remedy.get("image.graphics", ()):
        selector = finding.details.get("selector")
        if selector:
            lines += [
                f"# [image.graphics.{json.dumps(selector)}]",
                '# title = ""',
                '# description = ""  # describe the image in context',
                f"# fingerprint = {json.dumps(finding.details.get('fingerprint', ''))}",
                "",
            ]
    return lines


ADAPTER = FamilyAdapter(
    name="image",
    family=Family.IMAGE,
    audit=audit_image,
    default_language=_language,
    set_default_language=_set_language,
    snapshot=_snapshot,
    preserved=_preserved,
    config_tables={"image": _parse},
    template=_template,
    review_items=(
        ReviewItem(
            "image meaning", "Whether the alternative conveys the image's purpose and information."
        ),
        ReviewItem(
            "source boundary",
            "Native standalone image export is unsupported; no Draw conversion is performed.",
        ),
    ),
)
