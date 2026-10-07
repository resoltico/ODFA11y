# SPDX-License-Identifier: MPL-2.0
"""Validate documents against the bundled, unmodified OASIS ODF Relax NG schemas."""

from __future__ import annotations

import hashlib
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

from .namespaces import qn

if TYPE_CHECKING:
    from .document import OdtDocument

SUPPORTED_VERSIONS = ("1.3", "1.4")
SCHEMA_DIRECTORY = Path(__file__).parent / "schemas"
MAIN_MEMBERS = ("content.xml", "styles.xml", "meta.xml", "settings.xml")
MANIFEST_MEMBER = "META-INF/manifest.xml"


@dataclass(frozen=True, slots=True)
class SchemaResult:
    """Violations found per member; ``version`` is None when the document declares none."""

    version: str | None
    available: bool
    violations: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """The total number of violations across members."""
        return sum(len(messages) for messages in self.violations.values())


@cache
def _validator(version: str, *, manifest: bool) -> etree.RelaxNG:
    name = f"OpenDocument-v{version}-{'manifest-schema' if manifest else 'schema'}.rng"
    return etree.RelaxNG(etree.parse(str(SCHEMA_DIRECTORY / name)))


def declared_version(document: OdtDocument) -> str | None:
    """Read the ODF version declared by content.xml.

    Returns
    -------
    str | None
        The ``office:version`` value, or None when absent or unreadable.

    """
    if not document.has("content.xml"):
        return None
    return document.tree("content.xml").getroot().get(qn("office", "version"))


def validate(document: OdtDocument) -> SchemaResult:
    """Validate every member against the schema for the declared version.

    Violation messages carry no line numbers or paths, so they can be compared across edits.

    Returns
    -------
    SchemaResult
        The violations per member, or ``available=False`` when no schema is bundled.

    """
    version = declared_version(document)
    if version not in SUPPORTED_VERSIONS:
        return SchemaResult(version=version, available=False)
    violations: dict[str, tuple[str, ...]] = {}
    for name in (*MAIN_MEMBERS, MANIFEST_MEMBER):
        if not document.has(name):
            continue
        validator = _validator(version, manifest=name == MANIFEST_MEMBER)
        if not validator.validate(document.tree(name)):
            violations[name] = tuple(error.message for error in validator.error_log)
    return SchemaResult(version=version, available=True, violations=violations)


def regressions(before: SchemaResult, after: SchemaResult) -> dict[str, tuple[str, ...]]:
    """Find violations present after an edit that were not present before it.

    Returns
    -------
    dict[str, tuple[str, ...]]
        New violation messages per member; empty when nothing regressed.

    """
    found: dict[str, tuple[str, ...]] = {}
    for member, messages in after.violations.items():
        extra = Counter(messages) - Counter(before.violations.get(member, ()))
        if extra:
            found[member] = tuple(sorted(extra.elements()))
    return found


def provenance() -> dict[str, dict[str, str]]:
    """Read the bundled schemas' source URLs and verify their SHA-256 digests.

    Returns
    -------
    dict[str, dict[str, str]]
        File name to its source URL and digest.

    Raises
    ------
    ValueError
        A bundled file no longer matches its recorded digest.

    """
    recorded = tomllib.loads((SCHEMA_DIRECTORY / "PROVENANCE.toml").read_text(encoding="utf-8"))
    result: dict[str, dict[str, str]] = {}
    for name, entry in recorded.items():
        actual = hashlib.sha256((SCHEMA_DIRECTORY / name).read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            msg = f"Bundled schema {name} does not match its recorded SHA-256"
            raise ValueError(msg)
        result[name] = {"url": entry["url"], "sha256": actual}
    return result
