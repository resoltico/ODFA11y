# SPDX-License-Identifier: MPL-2.0
"""Generate published reference artifacts from their typed authorities."""

import argparse
import json
from pathlib import Path
from typing import cast

from odfa11y.cli.parser import build_parser
from odfa11y.concepts.review import ReviewTopic
from odfa11y.contracts import JsonObject
from odfa11y.decisions import DecisionScope
from odfa11y.decisions.edit import Status
from odfa11y.errors import RemedyAction
from odfa11y.families.probes import CapabilityStatus, ProbeId
from odfa11y.families.text.tables.classification import TableKind
from odfa11y.glossary import TERMS
from odfa11y.odf import Family, Layout, Part, Use
from odfa11y.plans.codec import decision_reference
from odfa11y.plans.registry import registered_kinds
from odfa11y.progress import Stage, Step, StepState
from odfa11y.remediate.violations import ViolationKind
from odfa11y.report import (
    RULES,
    ReportKind,
)
from odfa11y.rules.registry import Severity
from odfa11y.schemas import generated_schemas, registered_contracts
from odfa11y.status import (
    EXIT_PRECEDENCE,
    BatchStatus,
    ExitStatus,
    RunStatus,
    SkipReason,
    StageStatus,
)
from odfa11y.status import Profile as AssuranceProfile

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[1] / "src/odfa11y/schemas"
FORMATS = {contract.name: contract.record for contract in registered_contracts()}


USER_ENUMS = (
    ExitStatus,
    AssuranceProfile,
    Stage,
    Step,
    StepState,
    ReviewTopic,
    Severity,
    RemedyAction,
    ReportKind,
    SkipReason,
    DecisionScope,
    Family,
    Layout,
    Part,
    Use,
    ProbeId,
    CapabilityStatus,
    TableKind,
    Status,
    ViolationKind,
    StageStatus,
    RunStatus,
    BatchStatus,
)


def schemas() -> dict[str, JsonObject]:
    """Derive all versioned JSON format schemas from registered record types.

    Returns
    -------
    dict[str, JsonObject]
        Generated schemas keyed by their public format names.

    """
    return generated_schemas()


def rule_reference() -> str:
    """Render one catalogue row per authoritative rule.

    Returns
    -------
    str
        The generated Markdown rule reference.

    """
    lines = [
        "# Rule reference",
        "",
        "Rules define each finding's identity, severity, category and possible decision kinds.",
        "Findings reference these rules; open decisions carry the human questions.",
        "The [registry](../src/odfa11y/rules/registry.py) is authoritative.",
        "",
        "## Registered rules",
        "",
        "| ID | Severity | Finding | Decision kinds |",
        "| --- | --- | --- | --- |",
    ]
    for rule in sorted(RULES.values(), key=lambda value: value.id):
        decisions = ", ".join(
            f"`{kind.id}`" for kind in registered_kinds().values() if rule in kind.resolves
        )
        lines.append(
            f"| `{rule.id}` | {rule.severity.value.title()} | {rule.title} | {decisions} |"
        )
    mapping = json.loads(
        (Path(__file__).resolve().parents[1] / "src/odfa11y/rules/renamed.json").read_text()
    )
    lines += [
        "",
        "## Renamed in the next release",
        "",
        "| Previous ID | Current IDs |",
        "| --- | --- |",
    ]
    lines.extend(
        "| `" + row["old"] + "` | " + ", ".join("`" + value + "`" for value in row["new"]) + " |"
        for row in mapping
    )
    return "\n".join(lines) + "\n\n"


def _actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return parser._actions


def _commands(action: argparse.Action) -> dict[str, argparse.ArgumentParser] | None:
    choices = action.choices
    if (
        isinstance(choices, dict)
        and choices
        and all(isinstance(parser, argparse.ArgumentParser) for parser in choices.values())
    ):
        return cast("dict[str, argparse.ArgumentParser]", choices)
    return None


def _argument_reference(parser: argparse.ArgumentParser) -> list[str]:
    lines = [
        "| Argument | Values | Required | Default / choices | Help |",
        "| --- | --- | --- | --- | --- |",
    ]
    for action in _actions(parser):
        if _commands(action) is not None or action.help == argparse.SUPPRESS:
            continue
        name = ", ".join(action.option_strings) or action.dest
        arity = str(action.nargs) if action.nargs is not None else "1"
        values = []
        if action.default is not None and action.default != argparse.SUPPRESS:
            values.append(str(action.default))
        if action.choices is not None:
            values.append("choices: " + ", ".join(str(value) for value in action.choices))
        help_text = (action.help or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{name}` | {arity} | {'yes' if action.required else 'no'} | "
            f"{'; '.join(values)} | {help_text} |"
        )
    return [*lines, ""]


def cli_reference() -> str:
    """Describe all commands/options and shared exit values from their actual definitions.

    Returns
    -------
    str
        Deterministic generated CLI reference, independent of terminal width.

    """
    parser = build_parser()
    lines = [
        "# Command reference",
        "",
        "Generated from the CLI parser and core outcome vocabulary.",
        "Use `odfa11y COMMAND --help` for executable examples.",
        "Values: 0 means a flag, 1 one value, + one or more, ? optional, * zero or more.",
        "",
        "## Global options",
        "",
    ]
    lines += _argument_reference(parser)
    for action in _actions(parser):
        commands = _commands(action)
        if commands is None:
            continue
        for name, command in commands.items():
            lines += [f"## {name}", "", command.description or "", ""]
            lines += _argument_reference(command)
    lines += ["## Exit statuses", "", "| Code | Outcome |", "| --- | --- |"]
    for status in ExitStatus:
        lines.append(f"| {int(status)} | {status.name.replace('_', ' ').title()} |")
    precedence = " > ".join(str(int(status)) for status in reversed(EXIT_PRECEDENCE))
    lines += [
        "",
        f"Aggregation precedence: **{precedence}**.",
        "",
        "A passing dry run can have `published=false`; a refused candidate exits 2.",
        "Execution errors retain status 3; invalid arguments/plans use 4.",
        "",
    ]
    return "\n".join(lines)


def schema_reference() -> str:
    """List shipped record schemas and their version values from generated contracts.

    Returns
    -------
    str
        Versioned machine-interface index.

    """
    lines = [
        "# JSON Schemas",
        "",
        "Draft 2020-12 schemas ship in `odfa11y/schemas`.",
        "Registered facts and decisions are closed vocabularies.",
        "",
        "| Interface | Schema version | Schema |",
        "| --- | --- | --- |",
    ]
    for contract in registered_contracts():
        lines.append(
            f"| `{contract.name}` | {contract.schema_version} | "
            f"[{contract.filename}](../src/odfa11y/schemas/{contract.filename}) |"
        )
    lines += [
        "",
        "CLI audit/comparison JSON contains report objects (or an array of them).",
        "The `audit` schema describes the root application's per-input result record.",
        "The `plan` schema describes the parsed TOML structure; its header owns `schema_version`.",
        "See [application API](API.md) and [evidence](EVIDENCE.md).",
        "",
    ]
    return "\n".join(lines)


def capability_reference() -> str:
    """Render scoped native capabilities from the committed doctor measurement.

    Returns
    -------
    str
        A measured capability matrix, without running native tools during generation.

    """
    record = json.loads((SCHEMA_DIRECTORY.parents[2] / "docs/measurements/doctor.json").read_text())
    toolchain = record["toolchain"]
    lines = [
        "# Measured native capabilities",
        "",
        f"Recorded with ODFA11y {record['odfa11y']} on `{record['platform']}`.",
        (
            f"LibreOffice {toolchain['libreoffice']['version']}; "
            f"veraPDF {toolchain['verapdf']['version']}."
        ),
        "[Doctor record](measurements/doctor.json) is the measurement authority.",
        "",
        "| Probe | Family | Result |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{result['id']}` | {result['family']} | {result['status']} |"
        for result in record["capabilities"]
    )
    lines += [
        "",
        "These verdicts apply to each probe's authored input and exporter identity.",
        "Unsupported results do not waive document-level PDF gates. Execution failures are",
        "reported separately and retried; only conclusive observations are batch-cached.",
        "Doctor measures every probe; pipelines select relevant family/decision probes.",
        "",
        "The [text-structure measurements](measurements/text-exports.json) additionally",
        "record fixture-specific roles and independent validator outcomes. Read the",
        "[accessibility boundaries](ACCESSIBILITY.md) before interpreting a machine pass.",
        "",
    ]
    return "\n".join(lines)


def glossary_reference() -> str:
    """Generate shared vocabulary from core definitions and enum meanings."""
    lines = ["# Glossary", "", "## Terms", "", "| Term | Meaning |", "| --- | --- |"]
    lines.extend(f"| {term} | {meaning} |" for term, meaning in sorted(TERMS.items()))
    for enum_type in USER_ENUMS:
        lines.extend(["", f"## {enum_type.__name__}", "", "| Value | Meaning |", "| --- | --- |"])
        lines.extend(f"| `{member.value}` | {member.meaning} |" for member in enum_type)
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write reference artifacts or fail when the committed copies are stale.

    Returns
    -------
    int
        Zero for current/generated references; one for stale check-mode outputs.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail instead of updating stale files."
    )
    args = parser.parse_args()
    stale = []
    artifacts = {
        SCHEMA_DIRECTORY / f"{name}.schema.json": json.dumps(
            schema, indent=2, sort_keys=True, ensure_ascii=False
        )
        + "\n"
        for name, schema in schemas().items()
    }
    plan_path = SCHEMA_DIRECTORY.parents[2] / "docs/PLAN.md"
    prose = plan_path.read_text(encoding="utf-8").split("<!-- generated decisions -->", 1)[0]
    artifacts[plan_path] = (
        prose.rstrip()
        + "\n\n<!-- generated decisions -->\n"
        + decision_reference(registered_kinds())
    )
    artifacts[plan_path.with_name("GLOSSARY.md")] = glossary_reference()
    artifacts[plan_path.with_name("CLI.md")] = cli_reference()
    artifacts[plan_path.with_name("SCHEMAS.md")] = schema_reference()
    artifacts[plan_path.with_name("CAPABILITIES.md")] = capability_reference()
    rules_path = plan_path.with_name("RULES.md")
    reading = rules_path.read_text(encoding="utf-8").split("## Reading findings", 1)[1]
    artifacts[rules_path] = rule_reference() + "## Reading findings" + reading
    for path, expected in artifacts.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                stale.append(str(path))
        else:
            path.write_text(expected, encoding="utf-8")
    if stale:
        parser.exit(1, "Stale generated references:\n" + "\n".join(stale) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
