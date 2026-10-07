# SPDX-License-Identifier: MPL-2.0
"""Define the command-line arguments for every command."""

from __future__ import annotations

import argparse
from pathlib import Path

from odfa11y import __version__


def build_parser() -> argparse.ArgumentParser:
    """Define supported commands and explicit remediation controls.

    Returns
    -------
    argparse.ArgumentParser
        The parser for all supported CLI commands.

    """
    parser = argparse.ArgumentParser(
        prog="odfa11y",
        description=(
            "Audit and conservatively remediate ODF 1.4 Writer documents "
            "for accessible PDF/UA workflows."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "audit", help="Audit an ODT package, semantics and PDF/UA-preflight properties."
    )
    p.add_argument("source", type=Path)
    p.add_argument("--target-version", default="1.4")
    p.add_argument(
        "--schema",
        type=Path,
        help="Optional official ODF Relax NG schema for content/styles/meta validation.",
    )
    p.add_argument(
        "--manifest-schema", type=Path, help="Optional official ODF manifest Relax NG schema."
    )
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument(
        "--strict", action="store_true", help="Return non-zero when warnings are present."
    )

    p = sub.add_parser("remediate", help="Apply conservative, text-preserving ODT remediations.")
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    _add_remediation_options(p)

    p = sub.add_parser(
        "styles", help="Report paragraph-style usage and effective spacing properties."
    )
    p.add_argument("source", type=Path)
    p.add_argument("--format", choices=("text", "json"), default="text")

    _add_verification_commands(sub)
    _add_pipeline_commands(sub)

    return parser


def _add_remediation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="TOML remediation configuration file.")
    parser.add_argument("--target-version", default=None, help="Target ODF version; normally 1.4.")
    parser.add_argument("--title", default=None)
    parser.add_argument(
        "--description", default=None, help="Optional document description/subject metadata."
    )
    parser.add_argument(
        "--language", default=None, help="BCP 47 language tag, e.g. en-GB or lt-LT."
    )
    parser.add_argument(
        "--linkify",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Turn visible plain URLs/emails into ODF hyperlink elements without changing text.",
    )
    parser.add_argument(
        "--remove-empty-spacers",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Remove empty body paragraphs that do not carry "
            "page/master-page semantics. May reflow layout."
        ),
    )
    parser.add_argument(
        "--table-header",
        action="append",
        default=[],
        metavar="TABLE=ROWS",
        help="Mark the first ROWS direct rows of TABLE as semantic header rows; repeat as needed.",
    )
    parser.add_argument(
        "--alt-map",
        type=Path,
        help="JSON map of frame name/image path to {title, description} accessible text.",
    )


def _add_verification_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "normalize-spacing",
        help="Copy spacing from one reference paragraph style to selected paragraph styles.",
    )
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument(
        "--reference-text",
        required=True,
        help="Text contained in the reference paragraph or heading.",
    )
    p.add_argument(
        "--target-style",
        action="append",
        required=True,
        help="Paragraph style to normalize; repeat as needed.",
    )
    p.add_argument(
        "--exact-reference",
        action="store_true",
        help="Require exact reference paragraph text rather than substring matching.",
    )
    p.add_argument("--include-headings", action="store_true")

    p = sub.add_parser(
        "export-pdfua", help="Export an ODT to PDF/UA-1 using LibreOffice's Writer PDF filter."
    )
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("--soffice", type=Path)
    p.add_argument("--timeout", type=int, default=120)

    p = sub.add_parser(
        "verify-pdf", help="Inspect PDF/UA structural invariants and optionally run veraPDF."
    )
    p.add_argument("pdf", type=Path)
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--strict", action="store_true")
    p.add_argument(
        "--verapdf",
        nargs="?",
        const="auto",
        help="Also validate with veraPDF PDF/UA-1; optionally supply executable path.",
    )

    p = sub.add_parser(
        "verify", help="Audit an ODT and, if supplied, its exported PDF/UA counterpart."
    )
    p.add_argument("source", type=Path)
    p.add_argument("--pdf", type=Path)
    p.add_argument("--schema", type=Path)
    p.add_argument("--manifest-schema", type=Path)
    p.add_argument("--target-version", default="1.4")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--verapdf", nargs="?", const="auto", help="Run veraPDF on --pdf as PDF/UA-1.")


def _add_pipeline_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "pipeline", help="Remediate, re-audit, export PDF/UA, verify, and optionally run veraPDF."
    )
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path, help="Output remediated ODT.")
    p.add_argument("--pdf", type=Path, required=True, help="Output PDF/UA file.")
    _add_remediation_options(p)
    p.add_argument("--schema", type=Path)
    p.add_argument("--manifest-schema", type=Path)
    p.add_argument("--soffice", type=Path)
    p.add_argument("--verapdf", nargs="?", const="auto")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--format", choices=("text", "json"), default="text")

    p = sub.add_parser(
        "doctor", help="Report runtime dependencies and external validators/exporters."
    )
    p.add_argument("--format", choices=("text", "json"), default="text")
