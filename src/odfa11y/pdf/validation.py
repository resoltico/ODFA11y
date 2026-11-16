# SPDX-License-Identifier: MPL-2.0
"""Interpret bounded veraPDF XML independently of native process execution."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Protocol

from lxml import etree

from odfa11y.contracts import Description
from odfa11y.errors import DIAGNOSTIC_CHARACTERS, ToolFailure
from odfa11y.report import Report
from odfa11y.rules import registry as rules
from odfa11y.rules.details import DETAIL_ITEMS
from odfa11y.safe_xml import parse_secure
from odfa11y.tool_identity import ToolIdentity

MAX_REPORT_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ValidationIdentity:
    version: str
    profile: str
    compliant: bool
    failed_rules: int


@dataclass(frozen=True, slots=True)
class ValidationMeasurements:
    """Measurements produced by pdf-validation analysis; None denotes unmeasured data."""

    producer: Literal["pdf-validation"] = field(default="pdf-validation", init=False)
    identity: Annotated[
        ValidationIdentity | None,
        Description("Validator identity, profile, verdict and failed-rule count."),
    ] = None


@dataclass(frozen=True, slots=True)
class FailedRule:
    """One failed validation rule with its standard clause and sample failing contexts."""

    specification: str
    clause: str
    test_number: str
    description: str
    failed_checks: int
    contexts: tuple[str, ...]
    messages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VeraPdfResult:
    """A completed validation: who ran, which profile, the verdict and the raw report."""

    identity: ToolIdentity
    profile: str
    compliant: bool
    failures: tuple[FailedRule, ...]
    raw_xml: str
    xml_root: etree._Element


class PdfValidator(Protocol):
    """The independent validator operation accepted by PDF checks."""

    def __call__(
        self,
        pdf: str | Path,
        *,
        executable: str | Path | None = None,
        flavour: str = "ua1",
        timeout: float,
    ) -> VeraPdfResult: ...


def add_verapdf_findings(report: Report, result: VeraPdfResult) -> None:
    """Record the verdict, validator identity and one finding per failed rule."""
    report.measure(
        ValidationMeasurements(
            identity=ValidationIdentity(
                result.identity.version, result.profile, result.compliant, len(result.failures)
            )
        )
    )
    for failure in result.failures:
        report.raise_(
            rules.PDFUA001,
            f"{failure.specification} clause {failure.clause} test {failure.test_number}: "
            f"{failure.description}",
            details={
                "specification": failure.specification,
                "clause": failure.clause,
                "test_number": failure.test_number,
                "failed_checks": failure.failed_checks,
                "contexts": list(failure.contexts),
                "messages": list(failure.messages),
            },
        )


def parse_validation(xml: bytes, stderr: str = "") -> VeraPdfResult:
    if len(xml) > MAX_REPORT_BYTES:
        message = f"veraPDF report exceeds {MAX_REPORT_BYTES} bytes"
        raise ToolFailure(message)
    try:
        raw_xml = xml.decode("utf-8")
        root = parse_secure(xml)
    except (UnicodeDecodeError, etree.XMLSyntaxError) as exc:
        msg = "Could not parse the veraPDF report as XML."
        raise ToolFailure(
            msg,
            details=(
                f"stdout={xml[:DIAGNOSTIC_CHARACTERS]!r}\nstderr={stderr[:DIAGNOSTIC_CHARACTERS]!r}"
            ),
        ) from exc
    reports = list(_elements(root, "validationReport"))
    if not reports:
        msg = "veraPDF report contains no validationReport element."
        raise ToolFailure(msg)
    unprocessed = [r.get("jobEndStatus") for r in reports if r.get("jobEndStatus") != "normal"]
    if unprocessed:
        msg = f"veraPDF could not process the PDF: {', '.join(map(str, unprocessed))}"
        raise ToolFailure(msg)
    if any(report.get("isCompliant") not in {"true", "false"} for report in reports):
        message = "veraPDF report has a malformed isCompliant value."
        raise ToolFailure(message)
    core = next(
        (n for n in _elements(root, "releaseDetails") if n.get("id") == "core"),
        None,
    )
    return VeraPdfResult(
        identity=ToolIdentity(
            "veraPDF", (core.get("version") if core is not None else None) or "unknown"
        ),
        profile=reports[0].get("profileName") or "unknown",
        compliant=all(r.get("isCompliant") == "true" for r in reports),
        failures=tuple(
            _failed_rule(rule)
            for report in reports
            for rule in _elements(report, "rule")
            if rule.get("status") == "failed"
        ),
        raw_xml=raw_xml,
        xml_root=root,
    )


def _failed_rule(rule: etree._Element) -> FailedRule:
    checks = [check for check in _elements(rule, "check") if check.get("status") == "failed"]
    shown = checks[:DETAIL_ITEMS]
    return FailedRule(
        specification=rule.get("specification") or "",
        clause=rule.get("clause") or "",
        test_number=rule.get("testNumber") or "",
        description=_child_text(rule, "description"),
        failed_checks=_failed_count(rule.get("failedChecks"), len(checks)),
        contexts=tuple(_child_text(check, "context") for check in shown),
        messages=tuple(_child_text(check, "errorMessage") for check in shown),
    )


def _elements(root: etree._Element, local_name: str):
    return (node for node in root.iter("*") if etree.QName(node).localname == local_name)


def _child_text(root: etree._Element, local_name: str) -> str:
    return next(
        (
            (node.text or "").strip()
            for node in root
            if isinstance(node.tag, str) and etree.QName(node).localname == local_name
        ),
        "",
    )


def _failed_count(value: str | None, observed: int) -> int:
    if value is None:
        return observed
    try:
        result = int(value) if re.fullmatch(r"[+-]?[0-9]+", value.strip()) else -1
        if result >= 0:
            return result
    except ValueError:
        pass
    message = "veraPDF report has a malformed failedChecks value."
    raise ToolFailure(message)
