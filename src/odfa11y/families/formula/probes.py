# SPDX-License-Identifier: MPL-2.0
"""Math's declared experiment checks tagging of an expression-only native document."""

from __future__ import annotations

lazy from pathlib import Path

from odfa11y.native.probe_pdf import math_tagging
from odfa11y.native.probe_sources import write_probe_package
from odfa11y.native.probes import CapabilityProbe, ProbeId
from odfa11y.odf import NS, Family


def write_math_probe(directory: Path) -> Path:
    """Write native MathML with an explicit spoken alternative.

    Returns
    -------
    Path
        The synthetic native Math package.

    """
    content = (
        f'<math:math xmlns:math="{NS["math"]}" alttext="x plus one" xml:lang="en-US">'
        "<math:semantics><math:mrow><math:mi>x</math:mi><math:mo>+</math:mo>"
        '<math:mn>1</math:mn></math:mrow><math:annotation encoding="StarMath 5.0">'
        "x + 1</math:annotation></math:semantics></math:math>"
    )
    return write_probe_package(
        directory / "expression.odf",
        "application/vnd.oasis.opendocument.formula",
        "",
        native_content=content,
    )


PROBES = (
    CapabilityProbe(
        ProbeId.MATH_TAGGING,
        Family.FORMULA,
        write_math_probe,
        "math_pdf_Export",
        math_tagging,
        frozenset({"formula.alternative"}),
        (
            "The expression-only Math export has tagged, reconciled content under "
            "basic PDF inspection."
        ),
    ),
)
