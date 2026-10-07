# SPDX-License-Identifier: MPL-2.0
"""Run veraPDF and turn its machine-validation report into findings."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from odfa11y.errors import ToolFailedError, ToolNotFoundError
from odfa11y.external_tools import ToolIdentity, find_executable, run_bounded
from odfa11y.report import Report, rules
from odfa11y.safe_xml import secure_xml_parser

MAX_REPORTED_CHECKS = 3
MAX_REPORT_BYTES = 32 * 1024 * 1024
DETAIL_CHARS = 4096


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


def find_verapdf(requested: str | Path | None = None) -> str:
    """Locate the veraPDF executable.

    Returns
    -------
    str
        The executable path.

    """
    return find_executable(requested, ("verapdf",))


def validate_pdfua(
    pdf: str | Path,
    *,
    executable: str | Path | None = None,
    flavour: str = "ua1",
    timeout: int = 180,
) -> VeraPdfResult:
    """Validate a PDF against a veraPDF profile and parse the XML report.

    A valid report is the outcome whatever the exit status; non-compliance is a result,
    not an error.

    Returns
    -------
    VeraPdfResult
        The verdict, failed rules and raw report.

    Raises
    ------
    ToolFailedError
        The validator times out, fails without a report, cannot process the PDF, or
        returns a report that is not valid veraPDF XML.

    """
    command = [
        find_verapdf(executable),
        "-f",
        flavour,
        "--format",
        "xml",
        "--loglevel",
        "0",
        str(Path(pdf).resolve()),
    ]
    try:
        completed = run_bounded(command, timeout=timeout, max_output=MAX_REPORT_BYTES)
    except subprocess.TimeoutExpired as exc:
        msg = f"veraPDF timed out after {timeout} s"
        raise ToolFailedError(msg) from exc
    if completed.truncated:
        msg = f"veraPDF output exceeded {MAX_REPORT_BYTES} bytes"
        raise ToolFailedError(msg)
    if completed.returncode != 0 and not completed.stdout.strip():
        msg = f"veraPDF failed (exit status {completed.returncode})."
        raise ToolFailedError(msg, details=completed.stderr.strip())
    return _parse(completed.stdout, completed.stderr)


def check_pdfua(
    pdf: str | Path, *, subject: str, executable: str | Path | None = None
) -> tuple[Report, VeraPdfResult | None]:
    """Validate a PDF and report the outcome, treating an unavailable validator as a warning.

    Returns
    -------
    tuple[Report, VeraPdfResult | None]
        A ``verapdf`` report (with ``VERA000`` when the validator cannot be found) and the
        parsed result, which is None when the validator was unavailable.

    """
    report = Report(kind="verapdf", subject=subject)
    try:
        located = find_verapdf(executable)
    except ToolNotFoundError as exc:
        report.add(rules.VERA000, str(exc))
        return report, None
    result = validate_pdfua(pdf, executable=located)
    add_verapdf_findings(report, result)
    return report, result


def add_verapdf_findings(report: Report, result: VeraPdfResult) -> None:
    """Record the verdict, validator identity and one finding per failed rule."""
    report.metadata["veraPDF"] = {
        "version": result.identity.version,
        "profile": result.profile,
        "compliant": result.compliant,
        "failed_rules": len(result.failures),
    }
    for failure in result.failures:
        report.add(
            rules.VERA001,
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


def _parse(stdout: str, stderr: str) -> VeraPdfResult:
    try:
        root = etree.fromstring(stdout.encode("utf-8"), parser=secure_xml_parser())
    except etree.XMLSyntaxError as exc:
        msg = "Could not parse the veraPDF report as XML."
        raise ToolFailedError(
            msg, details=f"stdout={stdout[:DETAIL_CHARS]!r}\nstderr={stderr[:DETAIL_CHARS]!r}"
        ) from exc
    reports = [node for node in root.iter("*") if etree.QName(node).localname == "validationReport"]
    if not reports:
        msg = "veraPDF report contains no validationReport element."
        raise ToolFailedError(msg)
    unprocessed = [r.get("jobEndStatus") for r in reports if r.get("jobEndStatus") != "normal"]
    if unprocessed:
        msg = f"veraPDF could not process the PDF: {', '.join(map(str, unprocessed))}"
        raise ToolFailedError(msg)
    core = next(
        (
            n
            for n in root.iter("*")
            if etree.QName(n).localname == "releaseDetails" and n.get("id") == "core"
        ),
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
            for rule in report.iter("rule")
            if rule.get("status") == "failed"
        ),
        raw_xml=stdout,
    )


def _failed_rule(rule: etree._Element) -> FailedRule:
    checks = [check for check in rule.iter("check") if check.get("status") == "failed"]
    shown = checks[:MAX_REPORTED_CHECKS]
    return FailedRule(
        specification=rule.get("specification") or "",
        clause=rule.get("clause") or "",
        test_number=rule.get("testNumber") or "",
        description=(rule.findtext("description") or "").strip(),
        failed_checks=int(rule.get("failedChecks") or len(checks)),
        contexts=tuple((check.findtext("context") or "").strip() for check in shown),
        messages=tuple((check.findtext("errorMessage") or "").strip() for check in shown),
    )
