# SPDX-License-Identifier: MPL-2.0
"""Execute the commands and map failures to exit statuses."""

from __future__ import annotations

import json
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
from odfa11y.audit import BLOCKING_RULE_IDS, audit_odf, render_template
from odfa11y.config import Config, load_config
from odfa11y.content import require_native_context
from odfa11y.errors import OdfA11yError, ToolNotFoundError, UnsupportedKindError
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import identify, termination_interrupt
from odfa11y.families import adapter_for
from odfa11y.families.text import ADAPTER as TEXT_ADAPTER
from odfa11y.families.text import write_link_probe
from odfa11y.fidelity import compare_pdfs
from odfa11y.odf import SUPPORTED_VERSIONS, OdfDocument
from odfa11y.pdf import (
    ExportSettings,
    export_pdfua,
    find_soffice,
    find_verapdf,
    identify_soffice,
    link_descriptions_supported,
)
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import remediate
from odfa11y.report import Report, exit_status, render_reports

from .audit import audit_command, command_gate, is_pdf
from .batch import batch_command
from .parser import build_parser

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

EXECUTION_FAILURE = 3


def main(argv: list[str] | None = None) -> int:
    """Run a command and return its documented exit status.

    Returns
    -------
    int
        Zero on success, 1 for strict warnings, 2 for findings, or 3 for execution failure.

    """
    args = build_parser().parse_args(argv)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "audit": audit_command,
        "batch": batch_command,
        "template": _template,
        "remediate": _remediate,
        "export": _export,
        "compare": _compare,
        "pipeline": _pipeline,
        "styles": _styles,
        "check-evidence": _check_evidence,
        "doctor": _doctor,
    }
    sarif = getattr(args, "format", None) == "sarif"
    try:
        with termination_interrupt():
            if sarif:
                if args.source_root is None:
                    print(
                        "error: SARIF requires an explicit source root (--source-root); "
                        "all inputs must be files within it.",
                        file=sys.stderr,
                    )
                    return EXECUTION_FAILURE
                _preflight_sarif(args)
            return handlers[args.command](args)
    except KeyboardInterrupt:
        print("error: command interrupted", file=sys.stderr)
        return EXECUTION_FAILURE
    except (OdfA11yError, OSError, ValueError) as exc:
        if sarif:
            print(
                "error: SARIF command failed; check source root, inputs and tools.", file=sys.stderr
            )
            return EXECUTION_FAILURE
        print(f"error: {exc}", file=sys.stderr)
        details = getattr(exc, "details", "")
        if details:
            print(details, file=sys.stderr)
        return EXECUTION_FAILURE


def _preflight_sarif(args: argparse.Namespace) -> None:
    sources = tuple(args.sources) if args.command == "audit" else (args.candidate, args.source)
    report = Report(kind="source", subject="", sources=sources)
    render_reports([report], output_format="sarif", source_root=args.source_root)


def _template(args: argparse.Namespace) -> int:
    report = audit_odf(args.source)
    blocking = Report(kind=report.kind, subject=report.subject)
    blocking.findings = [f for f in report.findings if f.rule_id in BLOCKING_RULE_IDS]
    if blocking.findings:
        print("No template: the document cannot be read well enough to plan.", file=sys.stderr)
        print(render_reports([blocking]), file=sys.stderr)
        return exit_status([blocking])
    adapter = adapter_for(OdfDocument.open(args.source).kind)
    print(render_template(report, adapter), end="")
    return 0


def _remediate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = remediate(args.source, args.destination, config.operations, dry_run=args.dry_run)
    if args.format == "json":
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0
    print("Dry run; nothing written." if args.dry_run else f"Wrote: {result.destination}")
    for outcome in result.outcomes:
        key = f" [{outcome.key}]" if outcome.key else ""
        print(f"- {outcome.status.value:9} {outcome.operation}{key}: {outcome.message}")
    if not result.outcomes:
        print("- No operations were configured.")
    print(f"Schema: {result.schema_check}")
    return 0


def _export(args: argparse.Namespace) -> int:
    settings = ExportSettings(_pdf_filter(args.source), args.soffice, args.timeout)
    print(export_pdfua(args.source, args.destination, settings))
    return 0


def _pdf_filter(path: Path) -> str:
    document = OdfDocument.open(path)
    pdf_filter = adapter_for(document.kind).pdf_filter
    if pdf_filter is None:
        kind = document.kind.name if document.kind is not None else "unrecognised"
        msg = f"No PDF export is defined for {kind} documents."
        raise UnsupportedKindError(msg)
    require_native_context(document)
    return pdf_filter


def _compare(args: argparse.Namespace) -> int:
    policy = (load_config(args.config) if args.config else Config()).fidelity
    source_pdf, candidate_pdf = is_pdf(args.source), is_pdf(args.candidate)
    with tempfile.TemporaryDirectory(prefix="odfa11y-compare-") as scratch:
        work = Path(scratch)
        left = _as_pdf(args.source, work / "source.pdf", args, work / "profile", is_pdf=source_pdf)
        right = _as_pdf(
            args.candidate, work / "candidate.pdf", args, work / "profile", is_pdf=candidate_pdf
        )
        report = compare_pdfs(left, right, policy, diff_dir=args.diff_dir)
    report.subject = f"{args.candidate.name} vs {args.source.name}"
    report.sources = (args.candidate, args.source)
    print(render_reports([report], output_format=args.format, source_root=args.source_root))
    status = exit_status([report], strict=args.strict)
    command_gate(args, status)
    return status


def _as_pdf(
    path: Path, rendered: Path, args: argparse.Namespace, profile: Path, *, is_pdf: bool
) -> Path:
    if is_pdf:
        return path
    settings = ExportSettings(_pdf_filter(path), args.soffice, args.timeout, profile)
    return export_pdfua(path, rendered, settings)


def _pipeline(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    options = PipelineOptions(
        profile=args.profile,
        soffice=str(args.soffice) if args.soffice else None,
        verapdf_path=str(args.verapdf_path) if args.verapdf_path else None,
        timeout=args.timeout,
    )
    record = run_pipeline(args.source, config.operations, config.fidelity, args.output_dir, options)
    if args.format == "json":
        print(json.dumps(record.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"Evidence: {args.output_dir}")
        for stage in record.stages:
            detail = f" ({stage.reason})" if stage.reason else ""
            print(f"- {stage.status:7} {stage.name}{detail}")
        reports = [s.report for s in record.stages if s.gate and s.report and not s.report.passed]
        if reports:
            print()
            print(render_reports(reports))
    return record.exit_status


def _styles(args: argparse.Namespace) -> int:
    document = OdfDocument.open(args.source)
    style_report = adapter_for(document.kind).style_report
    if style_report is None:
        kind = document.kind.name if document.kind is not None else "unrecognised"
        msg = f"A style report is not defined for {kind} documents."
        raise UnsupportedKindError(msg)
    rows = style_report(document)
    if args.format == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    print(f"Paragraph styles in {args.source}:")
    for row in rows:
        print(
            f"- {row['style']}: {row['count']} use(s); parent={row['parent']!r}; "
            f"spacing={row['spacing']}"
        )
    return 0


def _check_evidence(args: argparse.Namespace) -> int:
    problems = check_bundle(args.directory)
    for problem in problems:
        print(problem)
    print("Evidence bundle is intact." if not problems else f"{len(problems)} problem(s) found.")
    return 2 if problems else 0


def _doctor(args: argparse.Namespace) -> int:
    info: dict[str, object] = {
        "odfa11y": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "lxml": etree.__version__,
        "pypdf": pypdf.__version__,
        "pypdfium2": pypdfium2.version.PYPDFIUM_INFO.version,
        "pillow": PIL.__version__,
        "odf_schemas": list(SUPPORTED_VERSIONS),
        "LibreOffice": _tool(lambda: identify_soffice(find_soffice(args.soffice)).version),
        "veraPDF": _tool(lambda: identify("veraPDF", find_verapdf(), ("--version",)).version),
    }
    status = 0
    try:
        info["pdfua_link_descriptions"] = _link_descriptions(args)
    except OdfA11yError as exc:
        info["pdfua_link_descriptions"] = None
        print(f"error: {exc}", file=sys.stderr)
        status = EXECUTION_FAILURE
    if args.format == "json":
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        for key, value in info.items():
            print(f"{key}: {value or 'not found'}")
    return status


def _link_descriptions(args: argparse.Namespace) -> str:
    pdf_filter = TEXT_ADAPTER.pdf_filter
    if pdf_filter is None:
        msg = "No PDF export is defined for text documents."
        raise UnsupportedKindError(msg)
    settings = ExportSettings(pdf_filter, args.soffice, args.timeout)
    with tempfile.TemporaryDirectory(prefix="odfa11y-doctor-") as scratch:
        probe = Path(scratch) / "probe.odt"
        write_link_probe(probe)
        return "supported" if link_descriptions_supported(probe, settings) else "unsupported"


def _tool(probe: Callable[[], str]) -> str | None:
    try:
        return probe()
    except ToolNotFoundError:
        return None
