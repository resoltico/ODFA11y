# SPDX-License-Identifier: MPL-2.0
"""Give graphics accessible titles and descriptions."""

from lxml import etree

from odfa11y.concepts.graphic_identity import GraphicIdentity
from odfa11y.concepts.graphic_styles import GraphicRoleEditor, decorative_problem
from odfa11y.decisions import Decision
from odfa11y.decisions.answers import GraphicAlternativeAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import NS, Part
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument

MIN_CONFLICTING_VALUES = 2
FIELDS = (("title", xml_names.SVG_TITLE), ("description", xml_names.SVG_DESC))


def _accessibility_position(frame: etree._Element, tag: str) -> int:
    """Find where the ODF schema allows ``svg:title`` or ``svg:desc`` in a frame.

    Returns
    -------
    int
        An index after the frame's content, with the title before the description and
        both ahead of any contour.

    """
    children = list(frame)
    title, desc = frame.find("svg:title", NS), frame.find("svg:desc", NS)
    if tag == xml_names.SVG_DESC and title is not None:
        return children.index(title) + 1
    if tag == xml_names.SVG_TITLE and desc is not None:
        return children.index(desc)
    fixed = {
        xml_names.SVG_TITLE,
        xml_names.SVG_DESC,
        xml_names.DRAW_CONTOUR_POLYGON,
        xml_names.DRAW_CONTOUR_PATH,
    }
    if frame.tag != xml_names.DRAW_FRAME:
        return int(bool(children and children[0].tag == xml_names.OFFICE_EVENT_LISTENERS))
    last_content = max(
        (index for index, child in enumerate(children) if child.tag not in fixed), default=-1
    )
    return last_content + 1


def edit_graphic(
    document: OdfDocument, decision: Decision[GraphicAlternativeAnswer]
) -> tuple[Outcome, ...]:
    """Apply a validated alternative to one canonically resolved graphic."""
    frame = resolved_node(document, decision)
    answer = decision.answer
    identity = GraphicIdentity(document, (frame,))
    if problem := identity.style_problem(frame):
        raise DocumentRefusal(problem)
    roles = GraphicRoleEditor(document)
    if answer.decorative is not None:
        problem = None
        if document.tree(Part.CONTENT).getroot().get(xml_names.OFFICE_VERSION) != "1.4":
            problem = "Explicit graphic roles require an explicitly selected ODF 1.4 document."
        if frame.tag == xml_names.DRAW_G:
            problem = "Explicit group role edits are unsupported."
        problem = problem or roles.role(frame).problem
        problem = problem or roles.change_problem(frame, decorative=answer.decorative)
        if answer.decorative:
            problem = problem or decorative_problem(frame)
        if problem:
            raise DocumentRefusal(problem)
    changed = set_description(frame, answer.title, answer.description)
    if answer.decorative is not None:
        changed = roles.set_role(frame, decorative=answer.decorative) or changed
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            "Set accessible graphic alternative."
            if changed
            else "Accessible alternative already matches.",
            target=decision.target_path,
            count=int(changed),
        ),
    )


def set_description(frame: etree._Element, title: str | None, description: str | None) -> bool:
    changed = False
    for value, tag in ((title, xml_names.SVG_TITLE), (description, xml_names.SVG_DESC)):
        if value is None:
            continue
        node = frame.find(tag)
        if node is not None and (node.text or "") == value:
            continue
        if node is None:
            node = etree.Element(tag)
            frame.insert(_accessibility_position(frame, tag), node)
        node.text = value
        changed = True
    return changed
