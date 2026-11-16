# SPDX-License-Identifier: MPL-2.0
"""Inspect dependency identities and the declared native exporter capabilities."""

import platform
import sys
lazy from collections.abc import Callable

import PIL
import pypdf
import pypdfium2
from lxml import etree

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.errors import DocumentRefusal, ToolUnavailable
from odfa11y.families import REGISTRY
from odfa11y.families.probes import CapabilityResult, CapabilityStatus, ProbeCache
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.odf import SUPPORTED_VERSIONS
from odfa11y.progress import ProgressEvent, Step, StepState
from odfa11y.records import DoctorRecord, Toolchain
from odfa11y.tool_identity import ToolIdentity
from odfa11y.version import __version__
lazy from odfa11y.errors import OdfA11yError
lazy from odfa11y.progress import ProgressObserver


def inspect_tools(
    tools: Tools | None = None,
    *,
    on_progress: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
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
    native_tools = native_tools or NativeTools()
    tools = tools or Tools()
    if on_progress:
        on_progress(ProgressEvent(Step.PROBE_TOOLCHAIN, StepState.RUNNING))
    executable = None
    missing_error = None
    try:
        executable = native_tools.locate(tools.soffice)
    except ToolUnavailable as exc:
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
            libreoffice=native_tools.identify(executable) if executable is not None else None,
            verapdf=_tool(
                lambda: native_tools.identify_validator(
                    "veraPDF", native_tools.validator(tools.verapdf), ("--version",)
                )
            ),
        ),
    )
    probes = tuple(probe for adapter in REGISTRY.values() for probe in adapter.probes)
    if not probes:
        return info, DocumentRefusal(
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
        return info, missing_error or ToolUnavailable(
            "LibreOffice is unavailable for capability probes."
        )
    cache = ProbeCache()
    first_error = None
    for probe in probes:
        execution = cache.run(
            probe,
            identity,
            ExportSettings(probe.export_filter, executable, tools.timeout),
            observer=on_progress,
            verapdf_path=tools.verapdf,
            export=native_tools.export,
            validate=native_tools.validate,
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
    except ToolUnavailable:
        return None
