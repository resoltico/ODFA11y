# SPDX-License-Identifier: AGPL-3.0-only
"""Prepared inputs and artifacts produced by the run's declared stages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from odfa11y.capture import CapturedSource
from odfa11y.decisions import Decision
from odfa11y.families.spec import FamilySpec
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.native.tools import ResolvedTools
from odfa11y.native.verapdf import Validator
from odfa11y.odf import OdfDocument
from odfa11y.pdf.fidelity.compare import FidelityResult, Rasterizer
from odfa11y.pdf.validation import VeraPdfResult
from odfa11y.plans import Plan
from odfa11y.progress import ProgressObserver
from odfa11y.remediate import Candidate
from odfa11y.report import Report
from odfa11y.status import Profile
lazy from odfa11y.pdf.structure.fonts import Font


class RunOperations(Protocol):
    @property
    def render(self) -> Rasterizer: ...

    @property
    def validate(self) -> Validator: ...

    def export(self, source: Path, destination: Path, settings: ExportSettings, /) -> Path: ...


@dataclass(frozen=True, slots=True)
class PdfArtifact:
    path: Path


@dataclass(frozen=True, slots=True)
class RunState:
    source: CapturedSource
    document: OdfDocument
    plan: Plan
    decisions: tuple[Decision, ...]
    family: FamilySpec
    tools: ResolvedTools
    operations: RunOperations
    profile: Profile
    observer: ProgressObserver | None
    work: Path
    source_report: Report | None = None
    audited_source: OdfDocument | None = None
    candidate: Candidate | None = None
    candidate_path: Path | None = None
    candidate_report: Report | None = None
    source_pdf: PdfArtifact | None = None
    candidate_pdf: PdfArtifact | None = None
    pdf_report: Report | None = None
    source_fonts: tuple[Font, ...] | None = None
    candidate_fonts: tuple[Font, ...] | None = None
    validation: VeraPdfResult | None = None
    fidelity: FidelityResult | None = None
