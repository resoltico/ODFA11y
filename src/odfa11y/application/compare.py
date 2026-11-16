# SPDX-License-Identifier: MPL-2.0
"""Compare original ODF/PDF documents through temporary native renders when needed."""

import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from odfa11y.application.io_errors import translate_io
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit.export import native_export_settings
from odfa11y.capture import capture_source
from odfa11y.contracts import JsonObject, JsonProperty, record_dict
from odfa11y.errors import PackageError
from odfa11y.odf import OdfDocument
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.plans import Plan
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import load_plan
from odfa11y.progress import ProgressObserver, Step, step
from odfa11y.report import Report, SarifOptions, exit_status
from odfa11y.status import ExitStatus
lazy from odfa11y.plans.fidelity import FidelityPolicy

PDF_MAGIC = b"%PDF"


def is_pdf(path: Path) -> bool:
    """Sniff four bytes from a regular input with a nonblocking descriptor.

    Returns
    -------
    bool
        Whether the input has the PDF signature.

    Raises
    ------
    PackageError
        The selected or opened input is nonregular.

    """
    if not stat.S_ISREG(path.stat().st_mode):
        msg = f"Input {path} must be a regular file (ordinary file aliases are supported)"
        raise PackageError(msg)
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            msg = f"Input {path} must be a regular file"
            raise PackageError(msg)
        return os.read(descriptor, len(PDF_MAGIC)) == PDF_MAGIC
    finally:
        os.close(descriptor)


def compare_documents(
    source: str | Path,
    candidate: str | Path,
    policy: FidelityPolicy,
    diff_dir: str | Path | None = None,
    tools: Tools | None = None,
    *,
    on_progress: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> Report:
    """Capture each input once and render ODF inputs with one resolved LibreOffice."""
    operations = native_tools or NativeTools()
    source, candidate = Path(source), Path(candidate)
    with (
        capture_source(source) as left,
        capture_source(candidate) as right,
        tempfile.TemporaryDirectory(prefix="odfa11y-compare-") as scratch,
    ):
        work = Path(scratch)
        documents = tuple(
            None if is_pdf(item.path) else OdfDocument.open(item.path) for item in (left, right)
        )
        resolved = (tools or Tools()).resolve(
            libreoffice=any(doc is not None for doc in documents), native_tools=operations
        )
        office = resolved.libreoffice
        settings = []
        for document in documents:
            if document is None:
                settings.append(None)
            elif office is None:
                message = "Comparison preparation did not resolve LibreOffice"
                raise ValueError(message)
            else:
                settings.append(
                    native_export_settings(
                        document, office, resolved.timeout, work / "profile", captured_identity=True
                    )
                )
        paths = []
        for item, prepared, kind, name in zip(
            (left, right),
            settings,
            (Step.EXPORT_SOURCE, Step.EXPORT_CANDIDATE),
            ("source", "candidate"),
            strict=True,
        ):
            if prepared is None:
                paths.append(item.path)
                continue
            rendered = work / (name + ".pdf")
            with step(on_progress, kind):
                operations.export(item.path, rendered, prepared)
            paths.append(rendered)
        with step(on_progress, Step.COMPARE_FIDELITY):
            report = compare_pdfs(
                paths[0], paths[1], policy, diff_dir=diff_dir, render=operations.render
            ).report
        report.subject = f"{candidate.name} vs {source.name}"
        report.sources = (candidate, source)
        return report


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """A fidelity report under an explicit acceptance policy."""

    schema_version: Literal[1] = field(default=1, init=False)

    report: Report
    strict: bool = False

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Return the comparison's effective acceptance status."""
        return exit_status([self.report], strict=self.strict)

    def as_sarif(self, options: SarifOptions) -> JsonObject:
        """Render fidelity findings against their original input identities."""
        return options.log((self.report,))

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@translate_io
def compare(
    source: str | Path,
    candidate: str | Path,
    *,
    tools: Tools | None = None,
    plan: Plan | str | Path | None = None,
    diff_dir: str | Path | None = None,
    strict: bool = False,
    sarif: SarifOptions | None = None,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> ComparisonResult:
    """Compare original ODF/PDF inputs under the selected fidelity policy.

    Returns
    -------
    ComparisonResult
        Fidelity findings and effective strict acceptance.

    """
    if sarif is not None:
        sarif.preflight((candidate, source))
    policy = (
        (plan if isinstance(plan, Plan) else load_plan(plan)).fidelity
        if plan is not None
        else Pagination.SAME()
    )
    return ComparisonResult(
        compare_documents(
            source,
            candidate,
            policy,
            diff_dir,
            tools or Tools(),
            on_progress=observer,
            native_tools=native_tools,
        ),
        strict,
    )
