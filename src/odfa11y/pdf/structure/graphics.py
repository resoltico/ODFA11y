# SPDX-License-Identifier: MPL-2.0
"""Reconcile described Figures with graphical operations on their declared pages."""

lazy from odfa11y.pdf.reading.structure import StructureNode


def described_graphics(
    nodes: list[StructureNode], painted: dict[tuple[int | None, int | None], set[int]]
) -> int:
    """Count reachable described Figures containing reconciled page graphic operations.

    Returns
    -------
    int
        Figures with a nonblank alternative and a matching own/descendant content reference.
        A bottom-up pass visits every structure edge once.

    """
    graphics: dict[int, bool] = {}
    count = 0
    for node in reversed(nodes):
        reconciled = any(
            reference.mcid in painted.get(reference.identity, ())
            for reference in node.marked_content
        ) or any(graphics[id(child)] for child in node.children)
        graphics[id(node)] = reconciled
        alternative = node.element.get("/Alt")
        if (
            node.role == "Figure"
            and isinstance(alternative, str)
            and alternative.strip()
            and reconciled
        ):
            count += 1
    return count
