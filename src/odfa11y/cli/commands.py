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
from odfa11y.audit import audit_odt, render_template
from odfa11y.config import Config, load_config
from odfa11y.errors import OdfA11yError, ToolNotFoundError
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import identify
from odfa11y.fidelity import compare_pdfs
from odfa11y.odf import SUPPORTED_VERSIONS, OdtDocument
from odfa11y.pdf import (
    audit_pdfua,
    check_pdfua,
    export_pdfua,
    find_soffice,
    find_verapdf,
    identify_soffice,
)
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import remediate
from odfa11y.report import exit_status, render_reports

from .parser import build_parser

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

    from odfa11y.report import Report

EXECUTION_FAILURE = 3
PDF_MAGIC = b"%PDF"


def main(argv: list[str] | None = None) -> int:
    """Run a command and return its documented exit status.

    Returns
    -------
    int
        Zero on success, 1 for strict warnings, 2 for findings, or 3 for execution failure.

    """
    args = build_parser().parse_args(argv)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "audit": _audit,
        "template": _template,
        "remediate": _remediate,
        "export": _export,
        "compare": _compare,
        "pipeline": _pipeline,
        "styles": _styles,
        "check-evidence": _check_evidence,
        "doctor": _doctor,
    }
    try:
        return handlers[args.command](args)
    except (OdfA11yError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXECUTION_FAILURE


def _is_pdf(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(len(PDF_MAGIC)) == PDF_MAGIC


def _audit(args: argparse.Namespace) -> int:
    reports: list[Report] = []
    for source in args.sources:
        if _is_pdf(source):
            reports.append(audit_pdfua(source))
            if args.verapdf or args.verapdf_path:
                report, _result = check_pdfua(
                    source, subject=str(source), executable=args.verapdf_path
                )
                reports.append(report)
        else:
            reports.append(audit_odt(source, schema=args.schema))
    print(render_reports(reports, output_format=args.format))
    return exit_status(reports, strict=args.strict)


def _template(args: argparse.Namespace) -> int:
    print(render_template(audit_odt(args.source)), end="")
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
    print(export_pdfua(args.source, args.destination, soffice=args.soffice, timeout=args.timeout))
    return 0


def _compare(args: argparse.Namespace) -> int:
    policy = (load_config(args.config) if args.config else Config()).fidelity
    with tempfile.TemporaryDirectory(prefix="odfa11y-compare-") as scratch:
        work = Path(scratch)
        left = _as_pdf(args.source, work / "source.pdf", args, work / "profile")
        right = _as_pdf(args.candidate, work / "candidate.pdf", args, work / "profile")
        report = compare_pdfs(left, right, policy, diff_dir=args.diff_dir)
    report.subject = f"{args.candidate.name} vs {args.source.name}"
    print(render_reports([report], output_format=args.format))
    return exit_status([report], strict=args.strict)


def _as_pdf(path: Path, rendered: Path, args: argparse.Namespace, profile: Path) -> Path:
    if _is_pdf(path):
        return path
    return export_pdfua(
        path, rendered, soffice=args.soffice, timeout=args.timeout, profile_dir=profile
    )


def _pipeline(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    options = PipelineOptions(
        soffice=str(args.soffice) if args.soffice else None,
        verapdf=args.verapdf,
        verapdf_path=str(args.verapdf_path) if args.verapdf_path else None,
        timeout=args.timeout,
        strict=args.strict,
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
    rows = OdtDocument.open(args.source).catalog.paragraph_usage()
    if args.format == "json":
        data = [
            {"style": r.style_name, "count": r.count, "parent": r.parent, "spacing": r.spacing}
            for r in rows
        ]
        print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    print(f"Paragraph styles in {args.source}:")
    for row in rows:
        print(
            f"- {row.style_name}: {row.count} use(s); parent={row.parent!r}; spacing={row.spacing}"
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
        "LibreOffice": _tool(lambda: identify_soffice(find_soffice()).version),
        "veraPDF": _tool(lambda: identify("veraPDF", find_verapdf(), ("--version",)).version),
    }
    if args.format == "json":
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        for key, value in info.items():
            print(f"{key}: {value or 'not found'}")
    return 0


def _tool(probe: Callable[[], str]) -> str | None:
    try:
        return probe()
    except ToolNotFoundError:
        return None
