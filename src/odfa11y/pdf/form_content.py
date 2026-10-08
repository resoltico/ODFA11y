# SPDX-License-Identifier: MPL-2.0
"""Inspect invoked Form streams in their resource and marked-content scopes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdf.generic import NumberObject, StreamObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_consumption import MAX_FORM_DEPTH, MAX_FORM_INVOCATIONS, dictionary, resolve
from odfa11y.pdf_content import ContentScan, scan_content

from .graphic_presence import page_images

if TYPE_CHECKING:
    from pypdf.generic import DictionaryObject


class FormScanner:
    """Collect stream-specific content from bounded invocations on one page."""

    def __init__(self) -> None:
        self.streams: dict[int | None, ContentScan] = {}
        self.invocations = 0

    def scan(
        self,
        data: bytes,
        resources: DictionaryObject,
        context: tuple[bool, bool] = (False, False),
        active: frozenset[int] = frozenset(),
    ) -> ContentScan:
        """Scan content and every invoked Form, returning actual graphical presence.

        Returns
        -------
        ContentScan
            Content in this scope; Form scopes are collected separately.

        """
        properties = dictionary(resources.get("/Properties"))

        def property_mcid(name: str) -> int | None:
            value = dictionary(properties.get(name)).get("/MCID")
            return int(value) if isinstance(value, NumberObject) else None

        def invoke(name: str, inherited: tuple[bool, bool]) -> bool:
            form = resolve(dictionary(resources.get("/XObject")).get(name))
            if not isinstance(form, StreamObject) or form.get("/Subtype") != "/Form":
                return False
            self.invocations += 1
            if (
                id(form) in active
                or len(active) >= MAX_FORM_DEPTH
                or self.invocations > MAX_FORM_INVOCATIONS
            ):
                msg = "PDF Form cycle, depth or invocation limit prevents complete inspection"
                raise ToolFailedError(msg)
            scope = form.indirect_reference
            if scope is None:
                msg = "Cannot inspect a Form without an indirect stream identity"
                raise ToolFailedError(msg)
            own = dictionary(form.get("/Resources")) if "/Resources" in form else resources
            child = self.scan(form.get_data(), own, inherited, active | {id(form)})
            accumulated = self.streams.setdefault(scope.idnum, ContentScan())
            accumulated.mcids.update(child.mcids)
            accumulated.graphical_mcids.update(child.graphical_mcids)
            accumulated.unmarked_text_operations += child.unmarked_text_operations
            return child.graphical_content

        holder = dictionary(None)
        holder.update({"/Resources": resources})
        return scan_content(
            data, property_mcid, page_images(holder), invoke=invoke, context=context
        )
