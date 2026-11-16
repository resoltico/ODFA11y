# SPDX-License-Identifier: MPL-2.0
"""Small native fakes passed explicitly to application and workflow entry points."""

from collections.abc import Callable
from pathlib import Path
from typing import Never

from odfa11y.application.native import NativeTools
from odfa11y.audit.validation import check_pdfua as check
from odfa11y.audit.validation import validate_pdfua as validate
from odfa11y.families.probes import ProbeId
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.native.tools import LibreOffice, VeraPdf
from odfa11y.native.verapdf import ValidationOutput
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.pdf import tagged_writer
from tests.fixtures.probes import fake_export
from tests.fixtures.verapdf import FAILED_RULE, REPORT


def validation_result(compliant: bool = True):
    """Return real report bytes so fake execution still exercises the XML interpreter."""

    xml = REPORT.format(
        status="normal",
        compliant=str(compliant).lower(),
        failed=0 if compliant else 1,
        rules="" if compliant else FAILED_RULE,
    )
    return ValidationOutput(xml.encode(), "", ToolIdentity("veraPDF", "test"))


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
        validate=lambda *_args, **_kwargs: validation_result(True),
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


def export_settings(pdf_filter, soffice=None, timeout=120, profile_dir=None):
    """Build resolved native settings from test-owned executable selections."""

    return ExportSettings(
        pdf_filter,
        LibreOffice(str(soffice or "soffice"), ToolIdentity("LibreOffice", "26.8.0.3")),
        timeout,
        profile_dir,
    )


def validator_tool(executable="verapdf"):

    return VeraPdf(str(executable), ToolIdentity("veraPDF", "9.9.9"))


def validate_pdfua(pdf, *, executable=None, timeout=120):
    """Invoke the XML composition using a test-owned resolved validator."""

    return validate(pdf, tool=validator_tool(executable), timeout=timeout)


def check_pdfua(pdf, *, subject, executable=None, timeout=120):

    return check(pdf, subject=subject, tool=validator_tool(executable), timeout=timeout)
