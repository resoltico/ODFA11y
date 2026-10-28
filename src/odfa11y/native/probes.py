# SPDX-License-Identifier: MPL-2.0
"""Declared native capability experiments and batch-lifetime identity caching."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import OdfA11yError, ToolFailedError
from odfa11y.outcomes import ProgressEvent, StepName, StepState
lazy from odfa11y.odf import Family

from .export import ExportSettings, export_pdfua

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.decisions import Decision
    from odfa11y.outcomes import ProgressObserver

    from .process import ToolIdentity

    SourceWriter = Callable[[Path], Path]
    Evaluation = Callable[[Path, str | Path | None, float], bool]
    Exporter = Callable[[Path, Path, ExportSettings], Path]


class ProbeId(StrEnum):
    """The five measured exporter capabilities."""

    LINK_DESCRIPTIONS = "link-descriptions"
    DECORATIVE_ROLE = "decorative-graphic-role"
    WRITER_HEADER_COLUMNS = "writer-header-columns"
    MATH_TAGGING = "math-tagging"
    CALC_PDFUA = "calc-pdfua"


class CapabilityStatus(StrEnum):
    """A measured answer, or an explicit absence of a tested answer."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    NOT_TESTED = "not-tested"


@dataclass(frozen=True, slots=True)
class CapabilityProbe:
    """One family's synthetic source, native filter and observable PDF criterion."""

    id: ProbeId
    family: Family
    source_writer: SourceWriter
    export_filter: str
    evaluate: Evaluation
    decision_kinds: frozenset[str]
    description: str

    def relevant(self, family: Family | None, decisions: Sequence[Decision]) -> bool:
        """Select the declared family and decision scope.

        Returns
        -------
        bool
            Whether this experiment informs the selected native workflow.

        """
        return self.family == family and (
            not self.decision_kinds
            or bool(self.decision_kinds & {decision.kind.id for decision in decisions})
        )


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """A scoped probe observation with the actual reporting tool identity."""

    id: ProbeId
    family: Family
    status: CapabilityStatus
    tool: ToolIdentity | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProbeExecution:
    """Retain a failed experiment's record and controlled error separately."""

    result: CapabilityResult
    error: OdfA11yError | None = None


class ProbeCache:
    """Reuse conclusive observations only within the caller-owned workflow lifetime."""

    def __init__(self) -> None:
        """Start with no observations from any executable identity."""
        self._results: dict[tuple[Path, ToolIdentity, CapabilityProbe], CapabilityResult] = {}

    def run(
        self,
        probe: CapabilityProbe,
        identity: ToolIdentity,
        settings: ExportSettings,
        *,
        verapdf_path: str | Path | None = None,
        observer: ProgressObserver | None = None,
        export: Exporter | None = None,
    ) -> ProbeExecution:
        """Export the synthetic case once per executable identity and probe.

        Returns
        -------
        ProbeExecution
            A conclusive result, or not-tested plus its controlled error.

        """
        executable = Path(settings.soffice or "soffice").resolve()
        key = (executable, identity, probe)
        if key in self._results:
            return ProbeExecution(self._results[key])
        if observer:
            observer(ProgressEvent(StepName.PROBE_CAPABILITIES, StepState.RUNNING))
        try:
            supported = _conduct(probe, settings, verapdf_path, export or export_pdfua)
        except OSError as exc:
            error = ToolFailedError("Capability probe I/O failed", details=str(exc))
            return self._not_tested(probe, identity, error, observer)
        except OdfA11yError as exc:
            return self._not_tested(probe, identity, exc, observer)
        result = CapabilityResult(
            probe.id,
            probe.family,
            CapabilityStatus.SUPPORTED if supported else CapabilityStatus.UNSUPPORTED,
            identity,
        )
        self._results[key] = result
        if observer:
            observer(ProgressEvent(StepName.PROBE_CAPABILITIES, StepState.PASSED))
        return ProbeExecution(result)

    @staticmethod
    def _not_tested(
        probe: CapabilityProbe,
        identity: ToolIdentity,
        error: OdfA11yError,
        observer: ProgressObserver | None,
    ) -> ProbeExecution:
        if observer:
            observer(ProgressEvent(StepName.PROBE_CAPABILITIES, StepState.FAILED))
        return ProbeExecution(
            CapabilityResult(
                probe.id, probe.family, CapabilityStatus.NOT_TESTED, identity, str(error)
            ),
            error,
        )


def _conduct(
    probe: CapabilityProbe, settings: ExportSettings, verapdf: str | Path | None, export: Exporter
) -> bool:
    with tempfile.TemporaryDirectory(prefix=f"odfa11y-probe-{probe.id}-") as directory:
        work = Path(directory)
        source = probe.source_writer(work)
        selected = ExportSettings(
            probe.export_filter, settings.soffice, settings.timeout, work / "profile"
        )
        pdf = export(source, work / "probe.pdf", selected)
        return probe.evaluate(pdf, verapdf, float(settings.timeout))
