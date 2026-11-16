# SPDX-License-Identifier: MPL-2.0
"""Environment inspection and doctor-only native capability measurement."""

import platform
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Literal

import PIL
import pypdf
import pypdfium2
from lxml import etree

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.contracts import JsonObject, JsonProperty, record_dict
from odfa11y.errors import Failure, IoFailure, OdfA11yError, ToolUnavailable
from odfa11y.families import REGISTRY
from odfa11y.families import probes as probe_operations
from odfa11y.families.probes import CapabilityResult, CapabilityStatus
from odfa11y.native.libreoffice import ExportSettings, require_supported_version
from odfa11y.native.tools import LibreOffice, Toolchain
from odfa11y.odf import SUPPORTED_VERSIONS
from odfa11y.progress import ProgressObserver
from odfa11y.status import ExitStatus, failure_status
from odfa11y.version import __version__


@dataclass(frozen=True, slots=True)
class UnavailableTool:
    """Operations blocked by one missing tool in this observed environment."""

    tool: Literal["LibreOffice", "veraPDF"]
    blocks: tuple[str, ...]
    selection: Literal["soffice", "verapdf"]


@dataclass(frozen=True, slots=True)
class DoctorResult:
    """Tool/dependency identities and measured capabilities for one environment."""

    odfa11y: str
    python: str
    platform: str
    libraries: dict[str, str]
    schema_versions: tuple[str, ...]
    toolchain: Toolchain
    capabilities: tuple[CapabilityResult, ...]
    schema_version: Literal[1] = field(default=1, init=False)
    _error: OdfA11yError | None = field(default=None, repr=False)

    @JsonProperty
    def unavailable(self) -> tuple[UnavailableTool, ...]:
        """Explain the use cases that need identities not established by doctor."""
        missing = []
        office = self.toolchain.libreoffice
        usable = office is not None
        if office is not None:
            try:
                require_supported_version(office)
            except ToolUnavailable:
                usable = False
        if not usable:
            missing.append(
                UnavailableTool(
                    "LibreOffice",
                    (
                        "Native PDF export",
                        "ODF comparison",
                        "PDF and production runs",
                    ),
                    "soffice",
                )
            )
        if self.toolchain.verapdf is None:
            missing.append(
                UnavailableTool(
                    "veraPDF", ("Production runs", "Independent PDF validation"), "verapdf"
                )
            )
        return tuple(missing)

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Return the environment inspection execution status."""
        return failure_status(self.error) if self.error else ExitStatus.PASSED

    def as_dict(self) -> JsonObject:
        """Serialize the typed environment record.

        Returns
        -------
        JsonObject
            Versioned tool, dependency and capability facts.

        """
        return record_dict(self)

    @property
    def error(self) -> OdfA11yError | None:
        """Return the controlled error retained with the observations."""
        return self._error

    @JsonProperty
    def failure(self) -> Failure | None:
        """Project the controlled error without interpreting presentation text."""
        return self._error.as_record() if self._error is not None else None


def doctor(
    *,
    tools: Tools | None = None,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> DoctorResult:
    """Report dependency identities and every declared experiment without gating document runs."""
    selection = tools or Tools()
    operations = native_tools or NativeTools()
    office = validator = None
    first_error = None
    try:
        executable = operations.locate(selection.soffice)
        identity = operations.identify(executable, timeout=selection.timeout)
        office = LibreOffice(executable, identity)
        require_supported_version(identity)
    except OdfA11yError as error:
        first_error = error
    except OSError as error:
        first_error = IoFailure.from_oserror(error)
    with suppress(OdfA11yError, OSError):
        validator = selection.resolve(verapdf=True, native_tools=operations).verapdf
    office_error = first_error
    results = []
    for family in REGISTRY.values():
        for probe in family.probes:
            if office is None or office_error is not None:
                results.append(
                    CapabilityResult.for_probe(
                        probe,
                        CapabilityStatus.NOT_TESTED,
                        office.identity if office else None,
                        office_error.message if office_error else "LibreOffice unavailable",
                    )
                )
            elif probe.requires_validator and validator is None:
                results.append(
                    CapabilityResult.for_probe(
                        probe, CapabilityStatus.NOT_TESTED, office.identity, "veraPDF unavailable"
                    )
                )
            else:
                execution = probe_operations.measure_probe(
                    probe,
                    office.identity,
                    ExportSettings(probe.export_filter, office, selection.timeout),
                    observer=observer,
                    verapdf=validator,
                    export=operations.export,
                    validate=operations.validate,
                )
                results.append(execution.result)
                first_error = first_error or execution.error
    return DoctorResult(
        __version__,
        sys.version.split()[0],
        platform.platform(),
        {
            "lxml": etree.__version__,
            "pypdf": pypdf.__version__,
            "pypdfium2": pypdfium2.version.PYPDFIUM_INFO.version,
            "pillow": PIL.__version__,
        },
        tuple(SUPPORTED_VERSIONS),
        Toolchain(office.identity if office else None, validator.identity if validator else None),
        tuple(results),
        _error=first_error,
    )
