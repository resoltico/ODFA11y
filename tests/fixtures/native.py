# SPDX-License-Identifier: MPL-2.0
"""Small native fakes passed explicitly to application and workflow entry points."""

from collections.abc import Callable
from pathlib import Path
from typing import Never

from odfa11y.application.native import NativeTools
from odfa11y.families.probes import ProbeId
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.pdf.validation import FailedRule, VeraPdfResult
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.pdf import tagged_writer
from tests.fixtures.probes import fake_export


def validation_result(compliant: bool = True) -> VeraPdfResult:
    failures = (
        ()
        if compliant
        else (
            FailedRule("ISO 14289-1:2014", "7.1", "1", "Controlled validation failure", 1, (), ()),
        )
    )
    return VeraPdfResult(ToolIdentity("veraPDF", "test"), "PDF/UA-1", compliant, failures, "")


def refusing(calls: list[object]) -> Callable[..., Never]:
    def refuse(*args: object, **kwargs: object) -> Never:
        calls.append((args, kwargs))
        message = "An ineligible operation reached the native boundary"
        raise AssertionError(message)

    return refuse


def exporting(source: Path, destination: Path, settings: ExportSettings) -> Path:
    probes = {
        "link.odt": ProbeId.LINK_DESCRIPTIONS,
        "decorative.odt": ProbeId.DECORATIVE_ROLE,
        "columns.odt": ProbeId.WRITER_HEADER_COLUMNS,
        "expression.odf": ProbeId.MATH_TAGGING,
        "table.ods": ProbeId.CALC_PDFUA,
    }
    if source.name in probes:
        return fake_export(probes[source.name], supported=True)(source, destination, settings)
    tagged_writer(["H1", "P"]).write(destination)
    return destination


def native_fakes() -> NativeTools:
    return NativeTools(
        export=exporting,
        locate=lambda requested: str(requested or "test-soffice"),
        validator=lambda requested: str(requested or "test-verapdf"),
        identify=lambda _, **_options: ToolIdentity("LibreOffice", "26.8.0.3"),
        identify_validator=lambda *_args, **_options: ToolIdentity("veraPDF", "test"),
    )


def recording(calls: list[object]) -> Callable[[Path, Path, ExportSettings], Path]:
    def export(source: Path, destination: Path, settings: ExportSettings) -> Path:
        calls.append(source)
        return exporting(source, destination, settings)

    return export
