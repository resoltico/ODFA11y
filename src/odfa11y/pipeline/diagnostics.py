# SPDX-License-Identifier: MPL-2.0
"""Inspect dependency identities and the declared native exporter capabilities."""

from __future__ import annotations

import platform
import sys
from typing import TYPE_CHECKING

import PIL
import pypdf
import pypdfium2
from lxml import etree

from odfa11y import __version__
from odfa11y.errors import ToolNotFoundError, UnsupportedKindError
from odfa11y.families import REGISTRY
from odfa11y.native.export import ExportSettings, find_soffice, identify_soffice
from odfa11y.native.probes import CapabilityResult, CapabilityStatus, ProbeCache
from odfa11y.native.process import identify
from odfa11y.odf import SUPPORTED_VERSIONS
from odfa11y.outcomes import ProgressEvent, StepName, StepState
from odfa11y.pdf import find_verapdf
from odfa11y.records import DoctorRecord, Toolchain

from .native import NativeOptions

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.errors import OdfA11yError
    from odfa11y.native.process import ToolIdentity


def inspect_tools(
    options: NativeOptions | None = None,
) -> tuple[DoctorRecord, OdfA11yError | None]:
    """Collect identities and test every declared capability, retaining partial facts.

    Missing tool identities are ``None``. Unsupported tool versions still fail identity
    inspection. Controlled probe errors accompany partial facts after all declared
    probes are attempted;
    neither an identity nor the probe establishes document accessibility or conformance.

    Returns
    -------
    tuple[DoctorRecord, OdfA11yError | None]
        Dependency/tool facts and the first controlled probe error, if any.

    """
    options = options or NativeOptions()
    if options.on_progress:
        options.on_progress(ProgressEvent(StepName.PROBE_TOOLCHAIN, StepState.RUNNING))
    executable = None
    missing_error = None
    try:
        executable = find_soffice(options.soffice)
    except ToolNotFoundError as exc:
        missing_error = exc
    info = DoctorRecord(
        odfa11y=__version__,
        python=sys.version.split()[0],
        platform=platform.platform(),
        libraries={
            "lxml": etree.__version__,
            "pypdf": pypdf.__version__,
            "pypdfium2": pypdfium2.version.PYPDFIUM_INFO.version,
            "pillow": PIL.__version__,
        },
        schema_versions=tuple(SUPPORTED_VERSIONS),
        toolchain=Toolchain(
            libreoffice=identify_soffice(executable) if executable is not None else None,
            verapdf=_tool(lambda: identify("veraPDF", find_verapdf(), ("--version",))),
        ),
    )
    probes = tuple(probe for adapter in REGISTRY.values() for probe in adapter.probes)
    if not probes:
        return info, UnsupportedKindError(
            "No capability probes are declared by the registered families."
        )
    identity = info.toolchain.libreoffice
    if identity is None or executable is None:
        info.toolchain.capabilities = tuple(
            CapabilityResult(
                probe.id, probe.family, CapabilityStatus.NOT_TESTED, None, "LibreOffice unavailable"
            )
            for probe in probes
        )
        return info, missing_error or ToolNotFoundError(
            "LibreOffice is unavailable for capability probes."
        )
    cache = ProbeCache()
    first_error = None
    for probe in probes:
        execution = cache.run(
            probe,
            identity,
            ExportSettings(probe.export_filter, executable, options.timeout),
            observer=options.on_progress,
        )
        info.toolchain.capabilities += (execution.result,)
        first_error = first_error or execution.error
    return info, first_error


def _tool(probe: Callable[[], ToolIdentity]) -> ToolIdentity | None:
    """Inspect one tool identity without treating a missing tool as a version.

    Returns
    -------
    ToolIdentity | None
        The tool identity, or None when its executable is missing.

    """
    try:
        return probe()
    except ToolNotFoundError:
        return None
