# SPDX-License-Identifier: MPL-2.0
"""Inspect dependency identities and the text family's named-link export capability."""

from __future__ import annotations

import platform
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import PIL
import pypdf
import pypdfium2
from lxml import etree

from odfa11y import __version__
from odfa11y.errors import OdfA11yError, ToolNotFoundError, UnsupportedKindError
from odfa11y.external_tools import identify
from odfa11y.families import REGISTRY
from odfa11y.odf import SUPPORTED_VERSIONS, Family
from odfa11y.pdf import (
    ExportSettings,
    find_soffice,
    find_verapdf,
    identify_soffice,
    link_descriptions_supported,
)

from .native import NativeOptions

if TYPE_CHECKING:
    from collections.abc import Callable


def inspect_tools(
    options: NativeOptions | None = None,
) -> tuple[dict[str, object], OdfA11yError | None]:
    """Collect identities and test named-link export, retaining facts if the probe fails.

    Missing tool identities are ``None``. Unsupported tool versions still fail identity
    inspection. The named-link probe returns its controlled error alongside partial facts;
    neither an identity nor the probe establishes document accessibility or conformance.

    Returns
    -------
    tuple[dict[str, object], OdfA11yError | None]
        Dependency and tool facts, plus the named-link probe error if it could not complete.

    """
    options = options or NativeOptions()
    if options.on_progress:
        options.on_progress("Inspect dependency and tool identities", "running")
    info: dict[str, object] = {
        "odfa11y": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "lxml": etree.__version__,
        "pypdf": pypdf.__version__,
        "pypdfium2": pypdfium2.version.PYPDFIUM_INFO.version,
        "pillow": PIL.__version__,
        "odf_schemas": list(SUPPORTED_VERSIONS),
        "LibreOffice": _tool(lambda: identify_soffice(find_soffice(options.soffice)).version),
        "veraPDF": _tool(lambda: identify("veraPDF", find_verapdf(), ("--version",)).version),
    }
    try:
        if options.on_progress:
            options.on_progress("Test named-link PDF export", "running")
        info["pdfua_link_descriptions"] = _link_descriptions(options)
    except OdfA11yError as exc:
        info["pdfua_link_descriptions"] = None
        return info, exc
    return info, None


def _link_descriptions(options: NativeOptions) -> str:
    """Use the registered text-family probe and filter.

    Returns
    -------
    str
        ``supported`` or ``unsupported`` after the native probe completes.

    Raises
    ------
    UnsupportedKindError
        The text family has no PDF filter or named-link probe.

    """
    adapter = REGISTRY[Family.TEXT]
    if adapter.pdf_filter is None or adapter.link_probe is None:
        msg = "No named-link PDF export probe is defined for text documents."
        raise UnsupportedKindError(msg)
    settings = ExportSettings(adapter.pdf_filter, options.soffice, options.timeout)
    with tempfile.TemporaryDirectory(prefix="odfa11y-doctor-") as scratch:
        probe = adapter.link_probe(Path(scratch))
        return "supported" if link_descriptions_supported(probe, settings) else "unsupported"


def _tool(probe: Callable[[], str]) -> str | None:
    """Inspect one tool identity without treating a missing tool as a version.

    Returns
    -------
    str | None
        The tool version, or None when its executable is missing.

    """
    try:
        return probe()
    except ToolNotFoundError:
        return None
