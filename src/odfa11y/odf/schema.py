# SPDX-License-Identifier: MPL-2.0
"""Validate documents against the bundled, unmodified OASIS ODF Relax NG schemas."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.errors import XmlParseError

from .detect import declared_version
from .namespaces import is_office_element, qn
from .storage import Part

if TYPE_CHECKING:
    from .document import OdfDocument

SUPPORTED_VERSIONS = ("1.3", "1.4")
SCHEMA_DIRECTORY = Path(__file__).parent / "schemas"
SCHEMA_PARTS = (Part.CONTENT, Part.STYLES, Part.META, Part.SETTINGS, Part.MANIFEST)
FINGERPRINT_LENGTH = 16
# Attributes ODFA11y itself rewrites when it relabels a document; they must not make a
# pre-existing violation look new.
FINGERPRINT_IGNORED_ATTRIBUTES = frozenset({qn("office", "version"), qn("manifest", "version")})


@dataclass(frozen=True, slots=True)
class Violation:
    """One schema violation, identified without positions so unrelated edits keep it stable.

    ``fingerprint`` hashes the message with the failing element's tag, attributes, parent
    and neighbouring tags; it is None when libxml2 gave no resolvable location.
    """

    message: str
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SchemaResult:
    """Violations found per member; ``version`` is None when the document declares none."""

    version: str | None
    available: bool
    violations: dict[str, tuple[Violation, ...]] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """The total number of violations across members."""
        return sum(len(found) for found in self.violations.values())

    @property
    def unlocated(self) -> int:
        """How many violations could not be tied to an element."""
        return sum(v.fingerprint is None for found in self.violations.values() for v in found)

    def messages(self) -> dict[str, tuple[str, ...]]:
        """List violation messages per member.

        Returns
        -------
        dict[str, tuple[str, ...]]
            The message of every violation, member by member.

        """
        return {
            member: tuple(v.message for v in found) for member, found in self.violations.items()
        }


@cache
def _validator(version: str, *, manifest: bool) -> etree.RelaxNG:
    name = f"OpenDocument-v{version}-{'manifest-schema' if manifest else 'schema'}.rng"
    return etree.RelaxNG(etree.parse(str(SCHEMA_DIRECTORY / name)))


def validate(document: OdfDocument) -> SchemaResult:
    """Validate every part against the schema for the declared version.

    Violations carry no line numbers or paths, so they can be compared across edits. A part
    whose root is not an office document root (a formula's MathML) has no schema here and
    is skipped.

    Returns
    -------
    SchemaResult
        The violations per member, or ``available=False`` when no schema is bundled.

    """
    version = declared_version(document)
    if version not in SUPPORTED_VERSIONS:
        return SchemaResult(version=version, available=False)
    violations: dict[str, tuple[Violation, ...]] = {}
    checked: set[str] = set()
    for part in SCHEMA_PARTS:
        member = document.member_name(part)
        if member is None or member in checked:
            continue
        checked.add(member)
        try:
            tree = document.tree(part)
        except XmlParseError:
            continue  # not well-formed: reported separately, nothing to validate
        manifest = part is Part.MANIFEST
        if not manifest and not is_office_element(tree.getroot()):
            continue
        validator = _validator(version, manifest=manifest)
        if not validator.validate(tree):
            violations[member] = tuple(_violation(tree, error) for error in validator.error_log)
    return SchemaResult(version=version, available=True, violations=violations)


def regressions(before: SchemaResult, after: SchemaResult) -> dict[str, tuple[str, ...]]:
    """Find violations present after an edit that were not present before it.

    Violations are matched by message and fingerprint, so a violation fixed in one place
    cannot hide an equal one introduced in another. libxml2 reports only the first error
    in a failing content model, which bounds what any comparison can see.

    Returns
    -------
    dict[str, tuple[str, ...]]
        New violation messages per member; empty when nothing regressed.

    """
    found: dict[str, tuple[str, ...]] = {}
    for member, current in after.violations.items():
        extra = Counter((v.message, v.fingerprint) for v in current) - Counter(
            (v.message, v.fingerprint) for v in before.violations.get(member, ())
        )
        if extra:
            found[member] = tuple(sorted(message for message, _ in extra.elements()))
    return found


def _violation(tree: etree._ElementTree, error: etree._LogEntry) -> Violation:
    element = _locate(tree, error.path)
    return Violation(
        error.message, None if element is None else _fingerprint(error.message, element)
    )


def _locate(tree: etree._ElementTree, path: str | None) -> etree._Element | None:
    if not path:
        return None
    namespaces = {prefix: uri for prefix, uri in tree.getroot().nsmap.items() if prefix}
    try:
        found = tree.xpath(path, namespaces=namespaces)
    except etree.XPathError:
        return None
    if isinstance(found, list) and found and isinstance(found[0], etree._Element):
        return found[0]
    return None


def _fingerprint(message: str, element: etree._Element) -> str:
    parent = element.getparent()
    payload = [
        message,
        _tag(element),
        sorted(
            (key, value)
            for key, value in element.attrib.items()
            if key not in FINGERPRINT_IGNORED_ATTRIBUTES
        ),
        _tag(parent),
        _tag(element.getprevious()),
        _tag(element.getnext()),
    ]
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
    return digest.hexdigest()[:FINGERPRINT_LENGTH]


def _tag(element: etree._Element | None) -> str | None:
    if element is None:
        return None
    return element.tag if isinstance(element.tag, str) else "#node"


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
