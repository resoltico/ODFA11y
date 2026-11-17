# SPDX-License-Identifier: AGPL-3.0-only
"""Database form, report and query description targets."""

from collections.abc import Iterator

from lxml import etree

from odfa11y.decisions.domain import TargetDomain
from odfa11y.families.database.descriptions import fingerprint, targets
from odfa11y.odf import OdfDocument
from odfa11y.targets import Fingerprint, TargetPath


def _objects(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for path, nodes in targets(document).items():
        for node in nodes:
            yield TargetPath(path), node


def _fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    del document
    return fingerprint(node)


OBJECTS = TargetDomain(_objects, _fingerprint)
