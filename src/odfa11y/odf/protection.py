# SPDX-License-Identifier: MPL-2.0
"""Immutable declarations of package protection, independent of body parsing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

from odfa11y.errors import PackageError

from .archive import is_unsafe_member_name
from .namespaces import qn
from .storage import Part

if TYPE_CHECKING:
    from .package import PackageStorage
    from .storage import OdfStorage


@dataclass(frozen=True, slots=True)
class PackageProtection:
    """Declared protection without signature validation or decryption.

    Blocked package views do not establish manifest declarations.
    """

    signatures: tuple[str, ...] = ()
    encrypted: bool = False
    malformed_manifest: str | None = None
    ambiguous_members: tuple[str, ...] = ()
    unsafe_members: tuple[str, ...] = ()

    @property
    def inspection_blocked(self) -> bool:
        """Whether protection or package names prevent an established inspection view."""
        return bool(
            self.encrypted
            or self.malformed_manifest
            or self.ambiguous_members
            or self.unsafe_members
        )


def inspect_protection(storage: OdfStorage) -> PackageProtection:
    """Inspect declarations before any document-kind or ciphertext access.

    Returns
    -------
    PackageProtection
        Declared protection and manifest parse failure, if present.

    """
    if storage.layout != "package":
        return PackageProtection()
    names = tuple(cast("PackageStorage", storage).member_names())
    signatures = tuple(
        name
        for name in dict.fromkeys(names)
        if name.startswith("META-INF/") and "signatures" in name.rsplit("/", 1)[-1]
    )
    protection = PackageProtection(
        signatures,
        ambiguous_members=tuple(
            sorted(name for name, count in Counter(names).items() if count > 1)
        ),
        unsafe_members=tuple(sorted({name for name in names if is_unsafe_member_name(name)})),
    )
    if protection.inspection_blocked:
        return protection  # No ZIP-member selection establishes manifest or body semantics.
    member = storage.member_for(Part.MANIFEST)
    if member is None or not storage.has(member):
        return protection
    try:
        root = storage.parse_xml(member).getroot()
    except PackageError as exc:
        return replace(protection, malformed_manifest=str(exc))
    if root.tag != qn("manifest", "manifest"):
        return replace(protection, malformed_manifest="Malformed manifest root.")
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
    return replace(protection, encrypted=encrypted)
