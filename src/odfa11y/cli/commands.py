# SPDX-License-Identifier: MPL-2.0
"""Execute the document audit and remediation commands."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odt
from odfa11y.pdf import audit_pdfua, export_pdfua
from odfa11y.remediation import normalize_paragraph_spacing, remediate_odt
from odfa11y.report import max_severity_exit_code, render_report

from .options import options_from_args
from .parser import build_parser
from .reporting import append_verapdf_result, doctor, print_multi_reports, style_report

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable, Sequence

    from odfa11y.remediation import RemediationResult
    from odfa11y.report import AuditReport


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a command and return its documented severity exit code.

    Returns
    -------
    int
        Zero on success, 1 for strict warnings, 2 for findings, or 3 for execution failure.

    """
    args = build_parser().parse_args(argv)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "audit": _audit,
        "remediate": _remediate,
        "styles": lambda args: style_report(args.source, args.format),
        "normalize-spacing": _normalize_spacing,
        "export-pdfua": _export,
        "verify-pdf": _verify_pdf,
        "verify": _verify,
        "pipeline": _pipeline,
        "doctor": lambda args: doctor(args.format),
    }
    try:
        return handlers[args.command](args)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


def _odt_report(args: argparse.Namespace) -> AuditReport:
    return audit_odt(
        args.source,
        target_version=args.target_version,
        schema=args.schema,
        manifest_schema=args.manifest_schema,
    )


def _audit(args: argparse.Namespace) -> int:
    report = _odt_report(args)
    print(render_report(report, output_format=args.format))
    return max_severity_exit_code(report, strict=args.strict)


def _print_remediation(result: RemediationResult) -> None:
    print(f"Wrote: {result.destination}")
    for change in result.changes:
        print(f"- {change}")
    if not result.changes:
        print("- No changes were necessary.")


def _remediate(args: argparse.Namespace) -> int:
    result = remediate_odt(args.source, args.destination, options=options_from_args(args))
    _print_remediation(result)
    return 0


def _normalize_spacing(args: argparse.Namespace) -> int:
    result = normalize_paragraph_spacing(
        args.source,
        args.destination,
        reference_text=args.reference_text,
        target_styles=args.target_style,
        contains=not args.exact_reference,
        include_headings=args.include_headings,
    )
    print(f"Wrote: {result.destination}")
    for change in result.changes:
        print(f"- {change}")
    return 0


def _export(args: argparse.Namespace) -> int:
    pdf = export_pdfua(args.source, args.destination, soffice=args.soffice, timeout=args.timeout)
    print(pdf)
    return 0


def _verify_pdf(args: argparse.Namespace) -> int:
    report = audit_pdfua(args.pdf)
    append_verapdf_result(report, args.pdf, args.verapdf)
    print(render_report(report, output_format=args.format))
    return max_severity_exit_code(report, strict=args.strict)


def _verify(args: argparse.Namespace) -> int:
    reports = [_odt_report(args)]
    if args.pdf:
        pdf_report = audit_pdfua(args.pdf)
        append_verapdf_result(pdf_report, args.pdf, args.verapdf)
        reports.append(pdf_report)
    return print_multi_reports(reports, args.format, strict=args.strict)


def _pipeline(args: argparse.Namespace) -> int:
    options = options_from_args(args)
    remediation = remediate_odt(args.source, args.destination, options=options)
    odt_report = audit_odt(
        args.destination,
        target_version=options.target_version or "1.4",
        schema=args.schema,
        manifest_schema=args.manifest_schema,
    )
    if max_severity_exit_code(odt_report, strict=args.strict):
        if args.format == "text":
            print("PDF export skipped because the ODT audit failed.")
        return print_multi_reports([odt_report], args.format, strict=args.strict)
    export_pdfua(args.destination, args.pdf, soffice=args.soffice)
    pdf_report = audit_pdfua(args.pdf)
    append_verapdf_result(pdf_report, args.pdf, args.verapdf)
    if args.format == "text":
        print(f"Remediated ODT: {remediation.destination}")
        for change in remediation.changes:
            print(f"- {change}")
        print(f"PDF/UA export: {args.pdf}")
        print()
    return print_multi_reports([odt_report, pdf_report], args.format, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
