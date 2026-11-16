# SPDX-License-Identifier: MPL-2.0
"""Define the final command surface with one help text per shared option."""

import argparse
import sys
from pathlib import Path
from typing import Never

from odfa11y import ExitStatus, InvalidOption, Profile, Tools, __version__

from . import writer
from .text import terminal_text

HELP = {
    "format": "Output representation (default: text).",
    "source": "Input document.",
    "destination": "Output file, distinct from the source.",
    "plan": "TOML plan with reviewed answers and a fidelity policy.",
    "output_dir": "Evidence output directory.",
    "soffice": "LibreOffice executable (default: PATH).",
    "verapdf": "veraPDF executable (default: PATH).",
    "replace": "Atomically replace an existing regular output file.",
    "source_root": "Confined source root, required for SARIF output.",
    "strict": "Reject warning findings as well as errors.",
}


class TerminalParser(argparse.ArgumentParser):
    def _print_message(self, message, file=None) -> None:
        if message:
            if file is sys.stderr:
                writer.err(message, end="")
            else:
                writer.out(message, end="")

    def error(self, message: str) -> Never:
        self.print_usage(sys.stderr)
        self.exit(ExitStatus.USAGE_ERROR, f"{self.prog}: error: {terminal_text(message)}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = TerminalParser(
        prog="odfa11y",
        description="Audit, review, remediate and verify accessible documents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        suggest_on_error=True,
        color=False,
        epilog=(
            "Workflow: audit, prepare a plan, review answers, remediate, run and verify evidence.\n"
            "Exit statuses: "
        )
        + "; ".join(f"{value.value}: {value.meaning}" for value in ExitStatus),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    p = _command(
        sub,
        "audit",
        "Inspect ODF or PDF inputs without changing them.",
        "odfa11y audit source.odt\nodfa11y audit exported.pdf --validate --strict",
    )
    p.add_argument("sources", nargs="+", type=Path, help="One or more input documents.")
    p.add_argument(
        "--schema", action="store_true", help="Validate ODF against its declared schema."
    )
    p.add_argument("--validate", action="store_true", help="Request independent PDF/UA validation.")
    _verapdf(p)
    _timeout(p)
    _report_options(p)

    p = _command(
        sub,
        "plan",
        "Prepare source-bound questions with inert unanswered blocks.",
        "odfa11y plan source.odt > plan.toml\nodfa11y plan edited.odt --from plan.toml",
    )
    _source(p)
    p.add_argument(
        "--from", dest="from_plan", type=Path, help="Carry answers whose bindings still match."
    )
    p.add_argument(
        "--all",
        dest="include_all",
        action="store_true",
        help="Include optional overrides not raised by findings.",
    )
    _format(p)

    p = _command(
        sub,
        "remediate",
        "Apply reviewed answers under preservation and schema guards.",
        "odfa11y remediate source.odt reviewed.odt --plan plan.toml --dry-run",
    )
    _source(p)
    p.add_argument("destination", type=Path, help=HELP["destination"])
    p.add_argument("--plan", type=Path, required=True, help=HELP["plan"])
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes and remaining findings without publishing.",
    )
    _replace(p)
    _format(p)

    p = _command(
        sub,
        "export",
        "Publish a guarded native PDF export.",
        "odfa11y export reviewed.odt publication.pdf\nodfa11y audit publication.pdf --validate",
    )
    _source(p)
    p.add_argument("destination", type=Path, help=HELP["destination"])
    _tools(p)
    _replace(p)
    _format(p)

    p = _command(
        sub,
        "compare",
        "Compare source and candidate fidelity under an explicit policy.",
        "odfa11y compare source.odt reviewed.odt --diff-dir differences",
    )
    _source(p)
    p.add_argument("candidate", type=Path, help="Candidate document to compare with the source.")
    p.add_argument("--plan", type=Path, help=HELP["plan"])
    p.add_argument("--diff-dir", type=Path, help="Directory for declared difference images.")
    _tools(p)
    _report_options(p)

    p = _command(
        sub,
        "run",
        "Prepare, remediate and retain selected assurance evidence.",
        "odfa11y run source.odt --plan plan.toml --output-dir evidence --profile pdf",
    )
    _source(p)
    p.add_argument("--plan", type=Path, required=True, help=HELP["plan"])
    _run_options(p)

    p = _command(
        sub,
        "batch",
        "Execute independent batch-file items and retain progress.",
        "odfa11y batch batch.toml --output-dir batch-evidence",
    )
    p.add_argument(
        "batch_file", type=Path, help="Batch file listing document IDs, source paths and plans."
    )
    _run_options(p)

    p = _command(
        sub,
        "verify-evidence",
        "Check recorded-file integrity without asserting accessibility.",
        "odfa11y verify-evidence evidence",
    )
    p.add_argument("directory", type=Path, help="Evidence bundle directory to verify.")
    _format(p)

    p = _command(
        sub,
        "doctor",
        "Measure native tool identities and scoped capability experiments.",
        "odfa11y doctor --format json",
    )
    _tools(p)
    _verapdf(p)
    _format(p)
    return parser


def _command(sub, name: str, description: str, examples: str):
    return sub.add_parser(
        name,
        help=description,
        description=description,
        epilog="Examples:\n" + examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        suggest_on_error=True,
        color=False,
    )


def _source(parser) -> None:
    parser.add_argument("source", type=Path, help=HELP["source"])


def _format(parser, *, findings: bool = False) -> None:
    parser.add_argument(
        "--format",
        choices=("text", "json", "sarif") if findings else ("text", "json"),
        default="text",
        help=HELP["format"],
    )


def _report_options(parser) -> None:
    _format(parser, findings=True)
    parser.add_argument("--strict", action="store_true", help=HELP["strict"])
    parser.add_argument("--source-root", type=Path, help=HELP["source_root"])


def _tools(parser) -> None:
    parser.add_argument("--soffice", type=Path, help=HELP["soffice"])
    _timeout(parser)


def _verapdf(parser) -> None:
    parser.add_argument("--verapdf", type=Path, help=HELP["verapdf"])


def _replace(parser) -> None:
    parser.add_argument("--replace", action="store_true", help=HELP["replace"])


def _timeout(parser) -> None:
    default = Tools().timeout
    parser.add_argument(
        "--timeout",
        type=_timeout_seconds,
        default=default,
        help=f"Seconds per native call (default: {default:g}).",
    )


def _timeout_seconds(value: str) -> float:
    try:
        return Tools(timeout=float(value)).timeout
    except (ValueError, InvalidOption) as error:
        message = (
            f"Invalid timeout {value!r}; require finite positive seconds within the portable range."
        )
        raise argparse.ArgumentTypeError(message) from error


def _profile_value(value: str) -> Profile:
    try:
        return Profile.parse(value)
    except InvalidOption as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _run_options(parser) -> None:
    parser.add_argument("--output-dir", type=Path, required=True, help=HELP["output_dir"])
    parser.add_argument(
        "--profile",
        type=_profile_value,
        choices=tuple(Profile),
        default=Profile.PDF,
        help="Assurance profile (default: pdf): "
        + "; ".join(f"{value.value}: {value.meaning}" for value in Profile),
    )
    _tools(parser)
    _verapdf(parser)
    _format(parser)
