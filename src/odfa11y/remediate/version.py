# SPDX-License-Identifier: MPL-2.0
"""Declare a different ODF version on every part of a document."""

from odfa11y.decisions import Decision
from odfa11y.decisions.answers import OdfVersionAnswer
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.odf import Part, is_office_element, select_elements
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument

VERSIONED_PARTS = (Part.CONTENT, Part.STYLES, Part.META, Part.SETTINGS)


def edit_version(
    document: OdfDocument, decision: Decision[OdfVersionAnswer]
) -> tuple[Outcome, ...]:
    """Relabel supported parts before checking the candidate against its selected schema."""
    version = decision.answer.version
    changed = 0
    for part in VERSIONED_PARTS:
        if document.has(part):
            root = document.tree(part).getroot()
            if is_office_element(root) and root.get(xml_names.OFFICE_VERSION) != version:
                root.set(xml_names.OFFICE_VERSION, version)
                changed += 1
    if document.has(Part.MANIFEST):
        root = document.tree(Part.MANIFEST).getroot()
        for node in (
            root,
            *select_elements(root, "./manifest:file-entry[@manifest:full-path='/']"),
        ):
            if node.get(xml_names.MANIFEST_VERSION) != version:
                node.set(xml_names.MANIFEST_VERSION, version)
                changed += 1
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            f"Declared ODF {version} in {changed} place(s)."
            if changed
            else f"Already declares ODF {version}.",
            count=changed,
        ),
    )
