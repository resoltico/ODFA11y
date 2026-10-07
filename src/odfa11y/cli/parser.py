# SPDX-License-Identifier: MPL-2.0
"""Define the command-line arguments for every command."""

from __future__ import annotations

import argparse
from pathlib import Path

from odfa11y import __version__
from odfa11y.report import FORMATS

DEFAULT_TIMEOUT_SECONDS = 120


def build_parser() -> argparse.ArgumentParser:
    """Define every command and its arguments.

    Returns
    -------
    argparse.ArgumentParser
        The parser for all supported CLI commands.

    """
    parser = argparse.ArgumentParser(
        prog="odfa11y",
        description="Audit, remediate and verify ODF Writer documents for accessible PDF/UA.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("audit", help="Audit ODT or PDF files without changing them.")
    p.add_argument("sources", nargs="+", type=Path)
    p.add_argument(
        "--schema", action="store_true", help="Validate ODT files against the ODF schema."
    )
    _add_verapdf(p, "Validate PDF files with veraPDF (PDF/UA-1).")
    _add_report_options(p)

    p = sub.add_parser("template", help="Print a commented configuration template for an ODT.")
    p.add_argument("source", type=Path)

    p = sub.add_parser("remediate", help="Apply the configured operations to an ODT.")
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("--config", type=Path, required=True, help="TOML configuration file.")
    p.add_argument("--dry-run", action="store_true", help="Report outcomes without writing.")
    p.add_argument("--format", choices=FORMATS, default="text")

    p = sub.add_parser("export", help="Export an ODT to PDF/UA with LibreOffice.")
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    _add_tool_options(p)

    p = sub.add_parser("compare", help="Compare two ODT or PDF files for fidelity.")
    p.add_argument("source", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("--config", type=Path, help="TOML file whose [fidelity] table sets the policy.")
    p.add_argument("--diff-dir", type=Path, help="Write images of pages that differ here.")
    _add_tool_options(p)
    _add_report_options(p)

    p = sub.add_parser("pipeline", help="Remediate, export, validate, compare and keep evidence.")
    p.add_argument("source", type=Path)
    p.add_argument("--config", type=Path, required=True, help="TOML configuration file.")
    p.add_argument("--output-dir", type=Path, required=True, help="Evidence directory to create.")
    _add_verapdf(p, "Validate the PDF with veraPDF (PDF/UA-1).")
    _add_tool_options(p)
    _add_report_options(p)

    p = sub.add_parser("styles", help="Report paragraph-style usage and effective spacing.")
    p.add_argument("source", type=Path)
    p.add_argument("--format", choices=FORMATS, default="text")

    p = sub.add_parser("check-evidence", help="Verify an evidence directory against its manifest.")
    p.add_argument("directory", type=Path)

    p = sub.add_parser("doctor", help="Show tool and dependency versions.")
    p.add_argument("--format", choices=FORMATS, default="text")
    return parser


def _add_report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=FORMATS, default="text")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too.")


def _add_tool_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--soffice", type=Path, help="LibreOffice executable.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)


def _add_verapdf(parser: argparse.ArgumentParser, help_text: str) -> None:
    parser.add_argument("--verapdf", action="store_true", help=help_text)
    parser.add_argument(
        "--verapdf-path", type=Path, help="veraPDF executable (implies --verapdf); default: PATH."
    )
