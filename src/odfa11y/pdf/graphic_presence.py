# SPDX-License-Identifier: MPL-2.0
"""Reconcile described Figures with graphical operations on their declared pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdf.generic import NumberObject, StreamObject

from .structure_walk import pdf_dictionary

if TYPE_CHECKING:
    from collections.abc import Callable

    from pypdf import PageObject

    from .structure_walk import StructureNode


def page_images(page: PageObject) -> Callable[[str], bool]:
    """Resolve invoked resource names to image streams with positive dimensions.

    Returns
    -------
    Callable[[str], bool]
        A structural image-resource predicate; it does not decode images or enter Forms.

    """
    objects = pdf_dictionary(pdf_dictionary(page.get("/Resources")).get("/XObject"))

    def is_image(name: str) -> bool:
        reference = objects.get(name)
        value = reference.get_object() if reference is not None else None
        if not isinstance(value, StreamObject) or value.get("/Subtype") != "/Image":
            return False
        width, height = value.get("/Width"), value.get("/Height")
        return (
            isinstance(width, NumberObject)
            and width > 0
            and isinstance(height, NumberObject)
            and height > 0
        )

    return is_image


def described_graphics(nodes: list[StructureNode], painted: dict[int, set[int]]) -> int:
    """Count reachable described Figures containing reconciled page graphic operations.

    Returns
    -------
    int
        Figures with a nonblank alternative and a matching own/descendant content reference.
        A bottom-up pass visits every structure edge once.

    """
    graphics: dict[int, bool] = {}
    count = 0
    for node in reversed(nodes):
        reconciled = any(
            reference.mcid in painted.get(reference.page_xref, ())
            for reference in node.marked_content
        ) or any(graphics[id(child)] for child in node.children)
        graphics[id(node)] = reconciled
        alternative = node.element.get("/Alt")
        if (
            node.role == "Figure"
            and isinstance(alternative, str)
            and alternative.strip()
            and reconciled
        ):
            count += 1
    return count
