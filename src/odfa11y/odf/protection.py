# SPDX-License-Identifier: MPL-2.0
"""Immutable declarations of package protection, independent of body parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from odfa11y.errors import PackageError

from .namespaces import qn
from .storage import Part

if TYPE_CHECKING:
    from .package import PackageStorage
    from .storage import OdfStorage


@dataclass(frozen=True, slots=True)
class PackageProtection:
    """Declared protection; this does not validate signatures or decrypt members."""

    signatures: tuple[str, ...] = ()
    encrypted: bool = False
    malformed_manifest: str | None = None


def inspect_protection(storage: OdfStorage) -> PackageProtection:
    """Inspect declarations before any document-kind or ciphertext access.

    Returns
    -------
    PackageProtection
        Declared protection and manifest parse failure, if present.

    """
    if storage.layout != "package":
        return PackageProtection()
    signatures = tuple(
        name
        for name in cast("PackageStorage", storage).member_names()
        if name.startswith("META-INF/") and "signatures" in name.rsplit("/", 1)[-1]
    )
    member = storage.member_for(Part.MANIFEST)
    if member is None or not storage.has(member):
        return PackageProtection(signatures)
    try:
        root = storage.parse_xml(member).getroot()
    except PackageError as exc:
        return PackageProtection(signatures, malformed_manifest=str(exc))
    if root.tag != qn("manifest", "manifest"):
        return PackageProtection(signatures, malformed_manifest="Malformed manifest root.")
    encrypted = any(
        node.tag
        in {
            qn("manifest", name)
            for name in (
                "encryption-data",
                "encrypted-key",
                "key-derivation",
                "start-key-generation",
                "keyinfo",
            )
        }
        for node in root.iter()
    )
    return PackageProtection(signatures, encrypted)
