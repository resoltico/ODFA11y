# SPDX-License-Identifier: MPL-2.0
"""Declared native capability experiments and batch-lifetime identity caching."""

import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
lazy from collections.abc import Callable

from odfa11y.contracts import JsonProperty
from odfa11y.errors import IoFailure, OdfA11yError
from odfa11y.native.libreoffice import ExportSettings, export_pdfua
from odfa11y.pdf.validation import PdfValidator
from odfa11y.progress import ProgressEvent, Step, StepState
from odfa11y.rules.registry import Rule
from odfa11y.tool_identity import ToolIdentity
lazy from odfa11y.odf import Family
lazy from odfa11y.progress import ProgressObserver

SourceWriter = Callable[[Path], Path]
Evaluation = Callable[[Path, str | Path | None, float, PdfValidator | None], bool]
Exporter = Callable[[Path, Path, ExportSettings], Path]


class ProbeId(StrEnum):
    """The five measured exporter capabilities."""

    LINK_DESCRIPTIONS = "link-descriptions"
    DECORATIVE_ROLE = "decorative-graphic-role"
    WRITER_HEADER_COLUMNS = "writer-header-columns"
    MATH_TAGGING = "math-tagging"
    CALC_PDFUA = "calc-pdfua"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.LINK_DESCRIPTIONS: "Measure whether accessible link descriptions survive export.",
            self.DECORATIVE_ROLE: (
                "Measure whether decorative graphics retain their nonsemantic role."
            ),
            self.WRITER_HEADER_COLUMNS: "Measure whether Writer column headers survive PDF export.",
            self.MATH_TAGGING: "Measure whether exported mathematics has usable tagged structure.",
            self.CALC_PDFUA: (
                "Measure whether a semantic Calc table passes PDF inspection and PDF/UA validation."
            ),
        }[self]


class CapabilityStatus(StrEnum):
    """A measured answer, or an explicit absence of a tested answer."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    NOT_TESTED = "not-tested"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.SUPPORTED: "The declared synthetic experiment established the capability.",
            self.UNSUPPORTED: "The declared synthetic experiment did not establish the capability.",
            self.NOT_TESTED: "The capability was not measured conclusively.",
        }[self]


@dataclass(frozen=True, slots=True)
class CapabilityProbe:
    """One family's synthetic source, native filter and observable PDF criterion."""

    id: ProbeId
    family: Family
    source_writer: SourceWriter
    export_filter: str
    evaluate: Evaluation
    rules: tuple[Rule, ...]
    description: str
    requires_validator: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """A scoped probe observation with the actual reporting tool identity."""

    id: ProbeId
    family: Family
    status: CapabilityStatus
    tool: ToolIdentity | None
    reason: str | None = None
    related_rules: tuple[str, ...] = ()

    @JsonProperty
    def meaning(self) -> str:
        return self.id.meaning

    @classmethod
    def for_probe(
        cls,
        probe: CapabilityProbe,
        status: CapabilityStatus,
        tool: ToolIdentity | None,
        reason: str | None = None,
    ) -> CapabilityResult:
        return cls(
            probe.id, probe.family, status, tool, reason, tuple(rule.id for rule in probe.rules)
        )


@dataclass(frozen=True, slots=True)
class ProbeExecution:
    """Retain a failed experiment's record and controlled error separately."""

    result: CapabilityResult
    error: OdfA11yError | None = None


def measure_probe(
    probe: CapabilityProbe,
    identity: ToolIdentity,
    settings: ExportSettings,
    *,
    verapdf_path: str | Path | None = None,
    observer: ProgressObserver | None = None,
    export: Exporter | None = None,
    validate: PdfValidator | None = None,
) -> ProbeExecution:
    if observer:
        observer(ProgressEvent(Step.PROBE_CAPABILITIES, StepState.RUNNING))
    try:
        supported = _conduct(
            probe, settings, verapdf_path, export or export_pdfua, validate=validate
        )
    except OSError as error:
        return _probe_failure(probe, identity, IoFailure.from_oserror(error), observer)
    except OdfA11yError as error:
        return _probe_failure(probe, identity, error, observer)
    result = CapabilityResult.for_probe(
        probe,
        CapabilityStatus.SUPPORTED if supported else CapabilityStatus.UNSUPPORTED,
        identity,
    )
    if observer:
        observer(ProgressEvent(Step.PROBE_CAPABILITIES, StepState.PASSED))
    return ProbeExecution(result)


def _probe_failure(probe, identity, error: OdfA11yError, observer) -> ProbeExecution:
    if observer:
        observer(ProgressEvent(Step.PROBE_CAPABILITIES, StepState.FAILED))
    return ProbeExecution(
        CapabilityResult.for_probe(probe, CapabilityStatus.NOT_TESTED, identity, error.message),
        error,
    )


def _conduct(
    probe: CapabilityProbe,
    settings: ExportSettings,
    verapdf: str | Path | None,
    export: Exporter,
    *,
    validate: PdfValidator | None,
) -> bool:
    with tempfile.TemporaryDirectory(prefix=f"odfa11y-probe-{probe.id}-") as directory:
        work = Path(directory)
        source = probe.source_writer(work)
        selected = ExportSettings(
            probe.export_filter, settings.soffice, settings.timeout, work / "profile"
        )
        pdf = export(source, work / "probe.pdf", selected)
        return probe.evaluate(pdf, verapdf, float(settings.timeout), validate)
