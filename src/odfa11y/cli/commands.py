# SPDX-License-Identifier: MPL-2.0
"""Execute the commands and map failures to exit statuses."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from odfa11y.audit import prepare_plan
from odfa11y.errors import OdfA11yError, PlanError
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import termination_interrupt
from odfa11y.fidelity import FidelityPolicy
from odfa11y.outcomes import ExitStatus, failure_status
from odfa11y.pipeline import NativeOptions, compare_documents, export_document, inspect_tools
from odfa11y.plans import load_plan
from odfa11y.remediation import remediate
from odfa11y.report import Report, exit_status, render_reports, terminal_text

from .audit import audit_command, command_gate
from .batch import batch_command
from .guidance import error_hint
from .parser import build_parser
from .pipeline import pipeline_command
from .progress import progress_callback
from .styles import styles_command

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable


def main(argv: list[str] | None = None) -> int:
    """Run a command and return its documented exit status.

    Returns
    -------
    int
        Zero on success, 1 for strict warnings, 2 for findings, or 3 for execution failure.

    """
    parser = build_parser()
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        parser.print_help(file=sys.stderr)
        parser.exit(ExitStatus.USAGE_ERROR)
    args = parser.parse_args(arguments)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "audit": audit_command,
        "batch": batch_command,
        "plan": _plan,
        "remediate": _remediate,
        "export": _export,
        "compare": _compare,
        "pipeline": pipeline_command,
        "styles": styles_command,
        "check-evidence": _check_evidence,
        "doctor": _doctor,
    }
    sarif = getattr(args, "format", None) == "sarif"
    try:
        with termination_interrupt():
            if sarif:
                if args.source_root is None:
                    print(  # noqa: T201  CLI output is the command interface.
                        "error: SARIF requires an explicit source root (--source-root); "
                        "all inputs must be files within it.",
                        file=sys.stderr,
                    )
                    return ExitStatus.USAGE_ERROR
                _preflight_sarif(args)
            return handlers[args.command](args)
    except KeyboardInterrupt:
        print("error: command interrupted", file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        return ExitStatus.EXECUTION_FAILURE
    except (OdfA11yError, OSError, ValueError) as exc:
        if sarif:
            print(  # noqa: T201  CLI output is the command interface.
                "error: SARIF command failed; check source root, inputs and tools.", file=sys.stderr
            )
            return failure_status(exc)
        print(f"error: {terminal_text(exc)}", file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        if isinstance(exc, PlanError) and getattr(args, "plan", None):
            print(f"Plan: {terminal_text(args.plan)}", file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        details = getattr(exc, "details", "")
        if details:
            print(terminal_text(details), file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        if hint := error_hint(args, exc):
            print(hint, file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        return failure_status(exc)


def _preflight_sarif(args: argparse.Namespace) -> None:
    sources = tuple(args.sources) if args.command == "audit" else (args.candidate, args.source)
    report = Report(kind="source", subject="", sources=sources)
    render_reports([report], output_format="sarif", source_root=args.source_root)


def _plan(args: argparse.Namespace) -> int:
    report, template = prepare_plan(args.source)
    if template is None:
        print("No plan: the document cannot be read well enough to plan.", file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        print(render_reports([report]), file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        return exit_status([report])
    print(template, end="")  # noqa: T201  CLI output is the command interface.
    return 0


def _remediate(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan)
    result = remediate(
        args.source, args.destination, plan, dry_run=args.dry_run, rebind=args.rebind
    )
    if args.format == "json":
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))  # noqa: T201  CLI output is the command interface.
        return result.exit_status
    print(  # noqa: T201  CLI output is the command interface.
        "Dry run; proposed changes only. Nothing written."
        if args.dry_run
        else f"Wrote: {terminal_text(result.destination)}"
        if result.published
        else "Not published; review the failed guards."
    )
    for outcome in result.outcomes:
        key = f" [{terminal_text(outcome.key)}]" if outcome.key else ""
        print(  # noqa: T201  CLI output is the command interface.
            f"- {outcome.status.value:9} {terminal_text(outcome.operation)}{key}: "
            f"{terminal_text(outcome.message)}"
        )
    for violation in result.violations:
        print(f"- {violation.kind}: {terminal_text(violation.message)}")  # noqa: T201  CLI output is the command interface.
    if not result.outcomes:
        print("- No operations were configured. Enable reviewed decisions in your TOML plan.")  # noqa: T201  CLI output is the command interface.
    print(  # noqa: T201  CLI output is the command interface.
        f"Schema: {terminal_text(result.schema.status)}; ODF {result.schema.version}; "
        f"{result.schema.before_count} before, {result.schema.after_count} after, "
        f"{result.schema.new_count} new"
    )
    return result.exit_status


def _export(args: argparse.Namespace) -> int:
    output = export_document(args.source, args.destination, _native_options(args))
    print(f"Wrote PDF: {terminal_text(output)}")  # noqa: T201  CLI output is the command interface.
    print("Next: audit the PDF with --verapdf --strict and review its accessibility.")  # noqa: T201  CLI output is the command interface.
    return 0


def _compare(args: argparse.Namespace) -> int:
    policy = load_plan(args.plan).fidelity if args.plan else FidelityPolicy()
    report = compare_documents(
        args.source, args.candidate, policy, args.diff_dir, _native_options(args)
    )
    status = exit_status([report], strict=args.strict)
    command_gate(args, status, scope="fidelity checks under the selected policy.")
    print(render_reports([report], output_format=args.format, source_root=args.source_root))  # noqa: T201  CLI output is the command interface.
    return status


def _native_options(args: argparse.Namespace) -> NativeOptions:
    return NativeOptions(
        soffice=args.soffice,
        timeout=args.timeout,
        on_progress=progress_callback(getattr(args, "format", "text")),
    )


def _check_evidence(args: argparse.Namespace) -> int:
    problems = check_bundle(args.directory)
    for problem in problems:
        print(terminal_text(problem))  # noqa: T201  CLI output is the command interface.
    print(  # noqa: T201  CLI output is the command interface.
        "Evidence integrity: verified against the recorded manifest."
        if not problems
        else f"Evidence integrity: failed ({len(problems)} problem(s))."
    )
    print("This checks recorded files and hashes. It does not establish accessibility or review.")  # noqa: T201  CLI output is the command interface.
    return 2 if problems else 0


def _doctor(args: argparse.Namespace) -> int:
    info, error = inspect_tools(_native_options(args))
    status = ExitStatus.EXECUTION_FAILURE if error else 0
    if error:
        print(f"error: {terminal_text(error)}", file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        if details := getattr(error, "details", ""):
            print(terminal_text(details), file=sys.stderr)  # noqa: T201  CLI output is the command interface.
        if args.format == "text" and (hint := error_hint(args, error)):
            print(hint, file=sys.stderr)  # noqa: T201  CLI output is the command interface.
    if args.format == "json":
        print(json.dumps(info.as_dict(), indent=2, sort_keys=True))  # noqa: T201  CLI output is the command interface.
    else:
        values = {
            "odfa11y": info.odfa11y,
            "python": info.python,
            "platform": info.platform,
            **info.libraries,
            "odf_schemas": ", ".join(info.schema_versions),
            "LibreOffice": info.toolchain.libreoffice.version
            if info.toolchain.libreoffice
            else "not found",
            "veraPDF": info.toolchain.verapdf.version if info.toolchain.verapdf else "not found",
            **{
                key: value if value is not None else "not tested (probe unavailable or failed)"
                for key, value in info.capabilities.items()
            },
        }
        for key, value in values.items():
            print(f"{key}: {terminal_text(value)}")  # noqa: T201  CLI output is the command interface.
        print(  # noqa: T201  CLI output is the command interface.
            "Scope: dependency identities and a link-description export probe; "
            "no conformance verdict."
        )
    return status
