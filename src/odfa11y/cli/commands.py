# SPDX-License-Identifier: MPL-2.0
"""Execute the commands and map failures to exit statuses."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import odfa11y as api
from odfa11y import (
    ExitStatus,
    OdfA11yError,
    PlanError,
    failure_status,
    render_reports,
    terminal_text,
)

from .audit import audit_command, command_gate
from .batch import batch_command
from .guidance import error_hint
from .parser import build_parser
from .pipeline import pipeline_command
from .progress import progress_callback

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
        "verify": _check_evidence,
        "doctor": _doctor,
    }
    sarif = getattr(args, "format", None) == "sarif"
    try:
        if sarif:
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
    api.preflight_sarif(sources, args.source_root)


def _plan(args: argparse.Namespace) -> int:
    result = api.plan(args.source)
    if result.template is None:
        print("No plan: the document cannot be read well enough to plan.", file=sys.stderr)  # noqa: T201  CLI output.
        print(render_reports([result.report]), file=sys.stderr)  # noqa: T201  CLI output.
    else:
        print(result.template, end="")  # noqa: T201  CLI output.
    return result.exit_status


def _remediate(args: argparse.Namespace) -> int:
    result = api.remediate(
        args.source, args.destination, args.plan, dry_run=args.dry_run, rebind=args.rebind
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
    result = api.export(
        args.source, args.destination, tools=_tools(args), observer=progress_callback("text")
    )
    output = result.output
    print(f"Wrote PDF: {terminal_text(output)}")  # noqa: T201  CLI output is the command interface.
    print("Next: audit the PDF with --verapdf --strict and review its accessibility.")  # noqa: T201  CLI output is the command interface.
    return result.exit_status


def _compare(args: argparse.Namespace) -> int:
    result = api.compare(
        args.source,
        args.candidate,
        plan=args.plan,
        diff_dir=args.diff_dir,
        tools=_tools(args),
        strict=args.strict,
        observer=progress_callback(args.format),
    )
    command_gate(args, result.exit_status, scope="fidelity checks under the selected policy.")
    print(render_reports([result.report], output_format=args.format, source_root=args.source_root))  # noqa: T201  CLI output.
    return result.exit_status


def _tools(args: argparse.Namespace) -> api.Tools:
    return api.Tools(
        soffice=getattr(args, "soffice", None),
        verapdf=getattr(args, "verapdf_path", None),
        timeout=args.timeout,
    )


def _check_evidence(args: argparse.Namespace) -> int:
    result = api.verify_evidence(args.directory)
    problems = result.problems
    for problem in problems:
        print(terminal_text(problem))  # noqa: T201  CLI output is the command interface.
    print(  # noqa: T201  CLI output is the command interface.
        "Evidence integrity: verified against the recorded manifest."
        if not problems
        else f"Evidence integrity: failed ({len(problems)} problem(s))."
    )
    print("This checks recorded files and hashes. It does not establish accessibility or review.")  # noqa: T201  CLI output is the command interface.
    return result.exit_status


def _doctor(args: argparse.Namespace) -> int:
    info = api.doctor(tools=_tools(args), observer=progress_callback(args.format))
    error = info.error
    status = info.exit_status
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
                f"{result.family.value}.{result.id.value}": result.status.value
                for result in info.toolchain.capabilities
            },
        }
        for key, value in values.items():
            print(f"{key}: {terminal_text(value)}")  # noqa: T201  CLI output is the command interface.
        print(  # noqa: T201  CLI output is the command interface.
            "Scope: dependency identities and declared scoped export probes; "
            "no conformance verdict."
        )
    return status
