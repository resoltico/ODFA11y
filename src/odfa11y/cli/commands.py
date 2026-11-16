# SPDX-License-Identifier: AGPL-3.0-only
"""Adapt command arguments to the nine use cases and render their typed results."""

import argparse
import sys
from collections.abc import Callable

import odfa11y as api

from . import writer
from .parser import build_parser
from .progress import progress_callback
from .text import (
    audit_next_step,
    remedy_hint,
    render_batch,
    render_doctor,
    render_remediation,
    render_reports,
    render_run,
    render_verdict,
    terminal_text,
)


def main(argv: list[str] | None = None, *, native_tools: api.NativeTools | None = None) -> int:
    parser = build_parser()
    selected = sys.argv[1:] if argv is None else argv
    if not selected:
        writer.err(parser.format_help(), end="")
        parser.exit(api.ExitStatus.USAGE_ERROR)
    args = parser.parse_args(selected)
    args.native_tools = native_tools
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "audit": _audit,
        "plan": _plan,
        "remediate": _remediate,
        "export": _export,
        "compare": _compare,
        "run": _run,
        "batch": _batch,
        "verify-evidence": _verify_evidence,
        "doctor": _doctor,
    }
    try:
        return handlers[args.command](args)
    except KeyboardInterrupt:
        writer.err("error: command interrupted")
        return api.ExitStatus.EXECUTION_FAILURE
    except OSError as error:
        return _failure(args, api.IoFailure.from_oserror(error))
    except api.OdfA11yError as error:
        return _failure(args, error)


def _failure(args, error) -> int:
    failure = api.sarif_failure(error) if args.format == "sarif" else error.as_record()
    writer.err("error: " + terminal_text(failure.message))
    for problem in failure.problems:
        writer.err("  - " + terminal_text(problem))
    if failure.details:
        writer.err(terminal_text(failure.details))
    if failure.remedy:
        writer.err(remedy_hint(failure.remedy))
    return failure.exit_status


def _tools(args) -> api.Tools:
    return api.Tools(
        soffice=getattr(args, "soffice", None),
        verapdf=getattr(args, "verapdf", None),
        timeout=args.timeout,
    )


def _sarif(args) -> api.SarifOptions | None:
    return api.SarifOptions(args.source_root) if args.format == "sarif" else None


def _audit(args) -> int:
    options = _sarif(args)
    result = api.audit(
        args.sources,
        tools=_tools(args),
        schema=args.schema,
        validate_pdf=args.validate,
        strict=args.strict,
        sarif=options,
        observer=progress_callback(args.format),
        native_tools=args.native_tools,
    )
    if options is None:
        for item in result.failures:
            writer.err(
                f"error: Cannot audit {terminal_text(item.source)}: {terminal_text(item.error)}"
            )
    if args.format == "json":
        writer.out(api.render_json(result.as_dict()))
    elif options:
        writer.out(api.render_json(result.as_sarif(options)))
    else:
        writer.out(render_reports(result.reports))
        writer.out(render_verdict(result.exit_status, strict=result.strict))
        if hint := audit_next_step(result):
            writer.out(hint)
    return result.exit_status


def _plan(args) -> int:
    result = api.plan(args.source, from_plan=args.from_plan, include_all=args.include_all)
    if args.format == "json":
        writer.out(api.render_json(result.as_dict()))
    elif result.template is not None:
        writer.out(result.template, end="")
    else:
        writer.err("No plan: source inspection could not establish a reviewable document.")
        writer.err(render_reports((result.report,)))
        writer.err(render_verdict(result.exit_status))
    return result.exit_status


def _remediate(args) -> int:
    result = api.remediate(
        args.source, args.destination, args.plan, dry_run=args.dry_run, replace=args.replace
    )
    writer.out(
        api.render_json(result.as_dict()) if args.format == "json" else render_remediation(result)
    )
    return result.exit_status


def _export(args) -> int:
    result = api.export(
        args.source,
        args.destination,
        tools=_tools(args),
        replace=args.replace,
        observer=progress_callback(args.format),
        native_tools=args.native_tools,
    )
    if args.format == "json":
        writer.out(api.render_json(result.as_dict()))
    else:
        writer.out("Wrote PDF: " + terminal_text(result.output))
        writer.out(render_verdict(result.exit_status))
    return result.exit_status


def _compare(args) -> int:
    options = _sarif(args)
    result = api.compare(
        args.source,
        args.candidate,
        tools=_tools(args),
        plan=args.plan,
        diff_dir=args.diff_dir,
        strict=args.strict,
        sarif=options,
        observer=progress_callback(args.format),
        native_tools=args.native_tools,
    )
    if args.format == "json":
        writer.out(api.render_json(result.as_dict()))
    elif options:
        writer.out(api.render_json(result.as_sarif(options)))
    else:
        writer.out(render_reports((result.report,)))
        writer.out(render_verdict(result.exit_status, strict=result.strict))
    return result.exit_status


def _run(args) -> int:
    result = api.run(
        args.source,
        args.plan,
        args.output_dir,
        tools=_tools(args),
        profile=args.profile,
        observer=progress_callback(args.format),
        native_tools=args.native_tools,
    )
    writer.out(
        api.render_json(result.as_dict())
        if args.format == "json"
        else render_run(result, args.output_dir)
    )
    return result.exit_status


def _batch(args) -> int:
    result = api.batch(
        args.batch_file,
        args.output_dir,
        tools=_tools(args),
        profile=args.profile,
        observer=progress_callback(args.format),
        native_tools=args.native_tools,
    )
    writer.out(
        api.render_json(result.as_dict())
        if args.format == "json"
        else render_batch(result, args.output_dir)
    )
    return result.exit_status


def _verify_evidence(args) -> int:
    result = api.verify_evidence(args.directory)
    if args.format == "json":
        writer.out(api.render_json(result.as_dict()))
    else:
        writer.out("\n".join(terminal_text(problem) for problem in result.problems))
        writer.out("Evidence integrity only; accessibility and human review are not established.")
        writer.out(render_verdict(result.exit_status))
    return result.exit_status


def _doctor(args) -> int:
    result = api.doctor(
        tools=_tools(args), observer=progress_callback(args.format), native_tools=args.native_tools
    )
    writer.out(
        api.render_json(result.as_dict()) if args.format == "json" else render_doctor(result)
    )
    if result.failure:
        writer.err("error: " + terminal_text(result.failure.message))
    return result.exit_status
