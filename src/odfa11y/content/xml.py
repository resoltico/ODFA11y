# SPDX-License-Identifier: MPL-2.0
"""Digest protected XML while a family declares exactly which metadata it may edit."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:
    from collections.abc import Collection


def protected_xml(
    element: etree._Element,
    *,
    omitted_elements: Collection[str] = (),
) -> str:
    """Hash all structure, references and content outside explicitly editable metadata.

    Returns
    -------
    str
        A full SHA-256 of the canonical protected XML.

    """
    copy = deepcopy(element)
    for node in list(copy.iter()):
        if node.tag in omitted_elements:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue
    return hashlib.sha256(etree.tostring(copy, method="c14n")).hexdigest()
