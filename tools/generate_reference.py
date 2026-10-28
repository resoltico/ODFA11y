# SPDX-License-Identifier: MPL-2.0
"""Generate published reference artifacts from their typed authorities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from odfa11y.adapter import Outcome, ReviewItem, Status
from odfa11y.application import AuditFailure, AuditInput, AuditRun
from odfa11y.batch.record import BatchItemResult, BatchRecord
from odfa11y.decisions import Decision, DecisionKind, DecisionScope, OpenDecision
from odfa11y.errors import OdfA11yError
from odfa11y.native.probes import CapabilityResult, CapabilityStatus, ProbeId
from odfa11y.native.process import ToolIdentity
from odfa11y.odf import Family
from odfa11y.outcomes import (
    BatchStatus,
    ExitStatus,
    ReviewTopic,
    RunStatus,
    StageName,
    StageStatus,
    ViolationKind,
)
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.profiles import Profile
from odfa11y.pipeline.record import RunRecord, StageResult
from odfa11y.plans import Plan, PlanHeader, SourceBinding
from odfa11y.plans.codec import decision_reference, decision_schema, plan_schema
from odfa11y.plans.registry import registered_kinds
from odfa11y.records import DoctorRecord, DocumentIdentity, SchemaCheck, Toolchain
from odfa11y.remediation import RemediationResult, Violation
from odfa11y.report import FACT_REGISTRY, RULES, FactSet, Finding, Location, Report, Rule
from odfa11y.serialization import JsonObject, JsonValue, schema_for

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[1] / "src/odfa11y/schemas"
FORMATS = {
    "report": Report,
    "audit": AuditRun,
    "run": RunRecord,
    "batch": BatchRecord,
    "doctor": DoctorRecord,
    "remediation": RemediationResult,
    "plan": Plan,
}
# Supply type-only names while resolving record annotations; runtime modules stay layered.
TYPE_NAMESPACE = {
    value.__name__: value
    for value in (
        AuditRun,
        AuditInput,
        AuditFailure,
        OdfA11yError,
        Outcome,
        ReviewItem,
        Status,
        BatchItemResult,
        BatchRecord,
        ToolIdentity,
        CapabilityResult,
        CapabilityStatus,
        ProbeId,
        Family,
        FidelityPolicy,
        BatchStatus,
        ExitStatus,
        ReviewTopic,
        RunStatus,
        StageName,
        StageStatus,
        ViolationKind,
        Profile,
        RunRecord,
        StageResult,
        DoctorRecord,
        DocumentIdentity,
        SchemaCheck,
        Toolchain,
        RemediationResult,
        FactSet,
        Finding,
        Rule,
        Location,
        Report,
    )
} | {
    "Plan": Plan,
    "Violation": Violation,
    "ViolationKind": ViolationKind,
    "PlanHeader": PlanHeader,
    "SourceBinding": SourceBinding,
    "OpenDecision": OpenDecision,
    "Decision": Decision,
    "DecisionKind": DecisionKind,
    "DecisionScope": DecisionScope,
    "JsonObject": JsonObject,
    "JsonValue": JsonValue,
    "Path": Path,
}


def schemas() -> dict[str, JsonObject]:
    """Derive all versioned JSON format schemas from registered record types.

    Returns
    -------
    dict[str, JsonObject]
        Generated schemas keyed by their public format names.

    """
    fact_properties: JsonObject = {
        key.id: schema_for(key.value_type, namespace=TYPE_NAMESPACE)
        | {"description": key.description}
        for key in FACT_REGISTRY.values()
    }
    kinds = registered_kinds()
    overrides: dict[object, JsonObject] = {
        Plan: plan_schema(kinds),
        Decision: decision_schema(kinds, open_decision=False),
        OpenDecision: decision_schema(kinds, open_decision=True),
        DecisionKind: {"enum": list(kinds)},
        FactSet: {"type": "object", "properties": fact_properties, "additionalProperties": False},
    }
    return {
        name: {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"urn:odfa11y:schema:{name}",
            **schema_for(record_type, namespace=TYPE_NAMESPACE, overrides=overrides),
        }
        for name, record_type in FORMATS.items()
    }


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
        "The [registry](../src/odfa11y/report/rules.py) is authoritative.",
        "",
        "## Registered rules",
        "",
        "| ID | Severity | Finding | Decision kinds |",
        "| --- | --- | --- | --- |",
    ]
    for rule in sorted(RULES.values(), key=lambda value: value.id):
        decisions = ", ".join(f"`{kind}`" for kind in rule.decision_kinds)
        lines.append(
            f"| `{rule.id}` | {rule.severity.value.title()} | {rule.title} | {decisions} |"
        )
    return "\n".join(lines) + "\n\n"


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
