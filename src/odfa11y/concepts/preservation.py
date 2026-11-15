# SPDX-License-Identifier: MPL-2.0
"""Preserve opaque package resources and flat embedded binary content across source edits."""

import hashlib
from dataclasses import dataclass

from odfa11y.odf import PackageStorage, Part
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


def opaque_payloads(document: OdfDocument) -> tuple[tuple[str, str], ...]:
    """Snapshot resources that accessibility operations never rewrite.

    Returns
    -------
    tuple[tuple[str, str], ...]
        Opaque member and embedded-data identities with content digests.

    """
    facts = []
    if isinstance(document.storage, PackageStorage):
        editable = {document.member_name(part) for part in Part}
        facts.extend(
            (name, hashlib.sha256(document.storage.read(name)).hexdigest())
            for name in document.storage.member_names()
            if name not in editable
        )
    for index, node in enumerate(document.tree(Part.CONTENT).iter(xml_names.OFFICE_BINARY_DATA)):
        value = "".join("".join(node.itertext()).split()).encode()
        facts.append((f"embedded[{index}]", hashlib.sha256(value).hexdigest()))
    return tuple(facts)


@dataclass(frozen=True, slots=True)
class PreservationSnapshot:
    """The family's immutable protected-content representation."""

    content: tuple[str, ...]
