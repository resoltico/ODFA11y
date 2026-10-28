# SPDX-License-Identifier: MPL-2.0
"""Define the command-line arguments for every command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Never

from odfa11y import __version__
from odfa11y.errors import PlanError
from odfa11y.external_tools import validate_timeout
from odfa11y.outcomes import ExitStatus
from odfa11y.pipeline import DEFAULT_PROFILE, DEFAULT_TIMEOUT_SECONDS, PROFILES
from odfa11y.report import FORMATS, terminal_text


class TerminalParser(argparse.ArgumentParser):
    """Keep native help and suggestions while escaping untrusted error messages."""

    def error(self, message: str) -> Never:
        """Print a terminal-safe parse error and exit with the shared usage status."""
        self.print_usage(sys.stderr)
        self.exit(ExitStatus.USAGE_ERROR, f"{self.prog}: error: {terminal_text(message)}\n")


def build_parser() -> argparse.ArgumentParser:
    """Define every command and its arguments.

    Returns
    -------
    argparse.ArgumentParser
        The parser for all supported CLI commands.

    """
    parser = TerminalParser(
        prog="odfa11y",
        description="Audit, remediate and verify ODF documents for accessible PDF/UA.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        suggest_on_error=True,
        color=False,
        epilog=(
            "Workflow (review decisions before changing a document):\n"
            "  odfa11y audit original.odt\n"
            "  odfa11y plan original.odt > document.toml\n"
            "  # Edit document.toml: uncomment only reviewed decisions.\n"
            "  odfa11y remediate original.odt reviewed.odt --plan document.toml --dry-run\n"
            "  odfa11y pipeline original.odt --plan document.toml \\\n"
            "    --output-dir evidence --profile production\n"
            "  odfa11y check-evidence evidence\n\n"
            "Use a new configuration filename and evidence directory.\n"
            "Exit statuses: 0 success; 1 gated warnings;\n"
            "  2 error findings; 3 execution failure; 4 invalid arguments/plans.\n"
            "A successful automated check still requires human accessibility review.\n"
            "Use odfa11y COMMAND --help for examples and options."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = _command(
        sub,
        "audit",
        examples=("  odfa11y audit source.odt\n  odfa11y audit exported.pdf --verapdf --strict"),
        description="Audit ODF or PDF files without changing them.",
    )
    p.add_argument("sources", nargs="+", type=Path)
    p.add_argument(
        "--schema", action="store_true", help="Validate ODF files against the ODF schema."
    )
    _add_verapdf(p, "Validate PDF files with veraPDF (PDF/UA-1).")
    _add_timeout(p)
    _add_report_options(p)

    p = _command(
        sub,
        "plan",
        examples=(
            "  odfa11y plan source.odt\n"
            "  odfa11y plan source.odt > plan.toml\n"
            "  # Use a new filename; edit and review the commented decisions."
        ),
        description="Print a source-bound plan of disabled human answers.",
    )
    p.add_argument("source", type=Path)

    p = _command(
        sub,
        "remediate",
        examples=(
            "  odfa11y remediate source.odt reviewed.odt --plan plan.toml --dry-run\n"
            "  odfa11y remediate source.odt reviewed.odt --plan plan.toml"
        ),
        description="Apply the configured operations to an ODF document.",
    )
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("--plan", type=Path, required=True, help="Source-bound TOML plan.")
    p.add_argument(
        "--rebind",
        action="store_true",
        help="Explicitly accept a different source digest; target fingerprints still apply.",
    )
    p.add_argument("--dry-run", action="store_true", help="Report outcomes without writing.")
    p.add_argument("--format", choices=("text", "json"), default="text")

    p = _command(
        sub,
        "export",
        examples=(
            "  odfa11y export reviewed.odt reviewed.pdf\n  odfa11y audit reviewed.pdf --verapdf"
        ),
        description="Export an ODF document to PDF/UA with LibreOffice.",
    )
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    _add_tool_options(p)

    p = _command(
        sub,
        "compare",
        examples=(
            "  odfa11y compare source.odt reviewed.odt --diff-dir differences\n"
            "  odfa11y compare original.pdf reviewed.pdf --strict"
        ),
        description="Compare two ODF or PDF files for fidelity.",
    )
    p.add_argument("source", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("--plan", type=Path, help="TOML file whose [fidelity] table sets the policy.")
    p.add_argument("--diff-dir", type=Path, help="Write images of pages that differ here.")
    _add_tool_options(p)
    _add_report_options(p)

    p = _command(
        sub,
        "pipeline",
        examples=(
            "  odfa11y pipeline source.odt --plan plan.toml --output-dir evidence\n"
            "  odfa11y pipeline source.odt --plan plan.toml \\\n"
            "    --output-dir production --profile production\n"
            "  # Review evidence/REVIEW.md; automated gates do not certify accessibility."
        ),
        description="Remediate, export, validate, compare and keep evidence.",
    )
    p.add_argument("source", type=Path)
    p.add_argument("--plan", type=Path, required=True, help="Source-bound TOML plan.")
    p.add_argument("--output-dir", type=Path, required=True, help="Evidence directory to create.")
    p.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default=DEFAULT_PROFILE,
        help=_profile_help(),
    )
    p.add_argument(
        "--verapdf-path", type=Path, help="veraPDF executable for the production profile."
    )
    _add_tool_options(p)
    p.add_argument("--format", choices=("text", "json"), default="text")

    p.add_argument(
        "--rebind", action="store_true", help="Explicitly rebind this plan to the selected source."
    )

    _add_batch(sub)

    p = _command(
        sub,
        "styles",
        examples=("  odfa11y styles source.odt\n  odfa11y styles source.odt --format json"),
        description="Report paragraph-style usage and effective spacing.",
    )
    p.add_argument("source", type=Path)
    p.add_argument("--format", choices=("text", "json"), default="text")

    p = _command(
        sub,
        "check-evidence",
        examples=(
            "  odfa11y check-evidence evidence\n"
            "  # Checks file integrity; read evidence/REVIEW.md for human review."
        ),
        description="Verify an evidence directory against its manifest.",
    )
    p.add_argument("directory", type=Path)

    p = _command(
        sub,
        "doctor",
        examples=("  odfa11y doctor\n  odfa11y doctor --soffice /path/to/soffice --format json"),
        description="Show tool and dependency versions and what the PDF export supports.",
    )
    _add_tool_options(p)
    p.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _add_report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=FORMATS, default="text")
    parser.add_argument(
        "--source-root", type=Path, help="Confined source root, required for SARIF."
    )
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too.")


def _add_tool_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--soffice", type=Path, help="LibreOffice executable.")
    _add_timeout(parser)


def _add_timeout(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_timeout_seconds,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Native tool timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )


def _timeout_seconds(value: str) -> int:
    try:
        seconds = int(value)
        validate_timeout(seconds)
    except (ValueError, PlanError) as exc:
        msg = (
            f"Invalid timeout: {value!r}; "
            "use positive whole seconds within the portable wait range."
        )
        raise argparse.ArgumentTypeError(msg) from exc
    return seconds


def _add_verapdf(parser: argparse.ArgumentParser, help_text: str) -> None:
    parser.add_argument("--verapdf", action="store_true", help=help_text)
    parser.add_argument(
        "--verapdf-path", type=Path, help="veraPDF executable (implies --verapdf); default: PATH."
    )


def _add_batch(sub: argparse._SubParsersAction) -> None:
    p = _command(
        sub,
        "batch",
        examples=(
            "  odfa11y batch manifest.toml --output-dir batch-evidence\n"
            "  odfa11y batch manifest.toml --output-dir production --profile production"
        ),
        description="Run independent manifest items and retain aggregate evidence.",
    )
    p.add_argument(
        "--rebind", action="store_true", help="Explicitly rebind each plan to its selected source."
    )
    p.add_argument("manifest", type=Path)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument(
        "--profile", choices=tuple(PROFILES), default=DEFAULT_PROFILE, help=_profile_help()
    )
    p.add_argument("--verapdf-path", type=Path)
    _add_tool_options(p)
    p.add_argument("--format", choices=("text", "json"), default="text")


def _profile_help() -> str:
    return (
        f"Assurance profile (default: {DEFAULT_PROFILE}): inspect checks source/remediation; "
        "verify adds PDF diagnostics and fidelity; production also requires veraPDF "
        "and gates warnings."
    )


def _command(
    sub: argparse._SubParsersAction, name: str, *, description: str, examples: str
) -> argparse.ArgumentParser:
    """Keep command descriptions and practical examples in native argparse help.

    Returns
    -------
    argparse.ArgumentParser
        The command parser with plain, suggestion-enabled help.

    """
    return sub.add_parser(
        name,
        help=description,
        description=description,
        epilog=f"Examples:\n{examples}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        suggest_on_error=True,
        color=False,
    )
