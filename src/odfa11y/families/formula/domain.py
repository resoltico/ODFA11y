# SPDX-License-Identifier: MPL-2.0
"""The one supported native mathematical-expression target."""

from collections.abc import Iterator

from lxml import etree

from odfa11y.decisions.domain import TargetDomain
from odfa11y.families.formula.expression import expression, fingerprint
from odfa11y.odf import OdfDocument
from odfa11y.targets import Fingerprint, TargetPath


def _expressions(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    root = expression(document)
    if root is not None:
        yield TargetPath("content/formula"), root


def _fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    del document
    return fingerprint(node)


FORMULA = TargetDomain(_expressions, _fingerprint)
