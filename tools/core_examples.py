# SPDX-License-Identifier: AGPL-3.0-only
"""Executable root-API examples, including outside-checkout installed-wheel qualification."""

lazy from pathlib import Path

import odfa11y as api


def inspect_source(source: Path, work: Path) -> list[api.Report]:
    """Inspect, prepare questions and apply one independently supplied example title.

    Returns
    -------
    list[api.Report]
        Completed source reports; each application result owns its effective status.

    Raises
    ------
    OdfA11yError
        The explicit reviewed edit could not be published.

    """
    work.mkdir(parents=True, exist_ok=True)
    inspected = api.audit(source, schema=True)
    completed = list(inspected.reports)
    prepared = api.plan(source)
    completed.append(prepared.report)
    if prepared.template is not None:
        (work / "decisions.toml").write_text(prepared.template, encoding="utf-8")
    kind = api.registered_kinds()["document.metadata"]
    answer = kind.answer_type(title="Reviewed example")
    decision = api.Decision(kind, None, answer)
    reviewed = api.Plan.for_source(source, [decision])
    result = api.remediate(source, work / ("reviewed" + source.suffix), reviewed)
    if result.exit_status != api.ExitStatus.PASSED:
        message = "The reviewed example could not be published."
        raise api.OdfA11yError(message)
    return completed


def native_work(
    source: Path, work: Path, tools: api.Tools
) -> tuple[api.Report, api.RunRecord, list[str]]:
    """Measure tools, export, compare and retain a complete assurance record.

    Returns
    -------
    tuple[Report, RunRecord, list[str]]
        Independent fidelity, run and recorded-file integrity results.

    """
    work.mkdir(parents=True, exist_ok=True)
    environment = api.doctor(tools=tools)
    if environment.error is not None:
        raise environment.error
    exported = api.export(source, work / "publication.pdf", tools=tools)
    comparison = api.compare(source, exported.output, tools=tools, diff_dir=work / "diff")
    record = api.run(source, api.Plan.for_source(source), work / "evidence", tools=tools)
    integrity = api.verify_evidence(work / "evidence")
    return comparison.report, record, list(integrity.problems)
