# SPDX-License-Identifier: MPL-2.0
"""Spreadsheet sheet identities shared by planning and editing."""

from collections.abc import Iterator

from lxml import etree

from odfa11y.decisions.domain import TargetDomain
from odfa11y.families.spreadsheet.sheets import sheets
from odfa11y.families.spreadsheet.snapshot import sheet_fingerprint
from odfa11y.odf import OdfDocument, Part
from odfa11y.targets import TargetPath


def _sheets(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for index, node in enumerate(sheets(document.tree(Part.CONTENT)), 1):
        yield TargetPath.indexed(Part.CONTENT, "sheet", index), node


SHEETS = TargetDomain(_sheets, sheet_fingerprint)
