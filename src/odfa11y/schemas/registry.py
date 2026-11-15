# SPDX-License-Identifier: MPL-2.0
"""The single catalogue of published result and plan-file contracts."""

from dataclasses import dataclass
from typing import get_args

from odfa11y.application import (
    AuditRun,
    ComparisonResult,
    ExportResult,
    PlanResult,
    VerificationResult,
)
from odfa11y.batch.record import BatchRecord
from odfa11y.contracts import JsonObject, schema_for
from odfa11y.contracts.types import computed_hints, record_hints, split
from odfa11y.decisions import Decision, OpenDecision
from odfa11y.plans import PlanHeader
from odfa11y.plans.contracts import decision_contract, file_contract
from odfa11y.plans.registry import registered_kinds
from odfa11y.records import DoctorRecord
from odfa11y.remediate import RemediationResult
from odfa11y.report import Report
from odfa11y.run.record import RunRecord


@dataclass(frozen=True, slots=True)
class RecordContract:
    """A record annotation, its schema filename and its authoritative version field."""

    name: str
    record: object
    version_owner: object | None = None

    @property
    def schema_version(self) -> int:
        owner = self.version_owner or self.record
        fields = record_hints(owner) | computed_hints(owner)
        annotation, _metadata = split(fields["schema_version"])
        return get_args(annotation)[0]

    @property
    def filename(self) -> str:
        return self.name + ".schema.json"


def registered_contracts() -> tuple[RecordContract, ...]:
    """Return schemas for every use case, the shared report and the plan file."""
    return (
        RecordContract("audit", AuditRun),
        RecordContract("plan", PlanResult),
        RecordContract("remediation", RemediationResult),
        RecordContract("export", ExportResult),
        RecordContract("comparison", ComparisonResult),
        RecordContract("run", RunRecord),
        RecordContract("batch", BatchRecord),
        RecordContract("evidence-verification", VerificationResult),
        RecordContract("doctor", DoctorRecord),
        RecordContract("report", Report),
        RecordContract("plan-file", file_contract(registered_kinds()), PlanHeader),
    )


def generated_schemas() -> dict[str, JsonObject]:
    """Generate published files from this registry and runtime annotations alone."""
    kinds = registered_kinds()
    overrides: dict[object, object] = {
        Decision: decision_contract(kinds, open_decision=False),
        OpenDecision: decision_contract(kinds, open_decision=True),
    }
    return {
        contract.name: {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:odfa11y:schema:" + contract.name,
            **schema_for(contract.record, input=contract.name == "plan-file", overrides=overrides),
        }
        for contract in registered_contracts()
    }
