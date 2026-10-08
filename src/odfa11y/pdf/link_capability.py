# SPDX-License-Identifier: MPL-2.0
"""Probe whether the installed LibreOffice describes hyperlinks in its PDF/UA export."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import ToolFailedError

from .audit import audit_pdfua
from .export import export_pdfua

if TYPE_CHECKING:
    from collections.abc import Callable

    from .export import ExportSettings

    Exporter = Callable[[Path, Path, ExportSettings], Path]


def link_descriptions_supported(
    document: str | Path, settings: ExportSettings, export: Exporter = export_pdfua
) -> bool:
    """Export a document whose content is a hyperlink and report whether the link is described.

    The PDF is judged by the same audit as any other: the answer is ``False`` exactly when
    the audit reports ``PDF019`` for the export. The export goes to a temporary directory.
    The built-in synthetic probe contains a navigational example.test link and no
    automatic-fetch resource. A supplied document/exporter can have other native behavior;
    this API does not enforce network isolation.

    Returns
    -------
    bool
        Whether the export describes the link, as PDF/UA requires.

    Raises
    ------
    ToolFailedError
        The export fails, or its PDF cannot be inspected. A missing LibreOffice raises
        ``ToolNotFoundError`` from the export.

    """
    with tempfile.TemporaryDirectory(prefix="odfa11y-link-probe-") as scratch:
        report = audit_pdfua(export(Path(document), Path(scratch) / "probe.pdf", settings))
    rule_ids = {finding.rule_id for finding in report.findings}
    if "PDF000" in rule_ids or not report.metadata.get("link_annotations"):
        msg = "The link probe's PDF cannot be inspected or contains no hyperlink."
        raise ToolFailedError(msg, details="\n".join(f.message for f in report.findings))
    return "PDF019" not in rule_ids
