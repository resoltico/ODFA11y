# SPDX-License-Identifier: MPL-2.0
"""The single catalogue of published result and plan-file contracts."""

from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Literal, get_args

from odfa11y.application import (
    AuditResult,
    ComparisonResult,
    ExportResult,
    PlanResult,
    VerificationResult,
)
from odfa11y.application.doctor import DoctorResult
from odfa11y.audit.engine import ExportContextMeasurements
from odfa11y.audit.package import PackageMeasurements
from odfa11y.batch.record import BatchRecord
from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.contracts import JsonObject, mapping_contract, schema_for
from odfa11y.contracts.types import computed_hints, record_hints, split
from odfa11y.decisions import Decision, OpenDecision
from odfa11y.families.chart.audit import ChartMeasurements
from odfa11y.families.database.audit import DatabaseMeasurements
from odfa11y.families.formula.audit import FormulaMeasurements
from odfa11y.families.image.audit import ImageMeasurements
from odfa11y.families.pages.audit import PageMeasurements
from odfa11y.families.spreadsheet.audit import SpreadsheetMeasurements
from odfa11y.families.text.audit import TextStyleMeasurements
from odfa11y.families.text.headings.audit import TextContentMeasurements
from odfa11y.families.text.language.audit import LanguageMeasurements
from odfa11y.families.text.lists.audit import ListMeasurements
from odfa11y.families.text.references.audit import ReferenceMeasurements
from odfa11y.families.text.tables.audit import TableMeasurements
from odfa11y.families.text.visibility.audit import VisibilityMeasurements
from odfa11y.families.text.visibility.reading_order import ReadingOrderMeasurements
from odfa11y.families.text.visibility.revisions import RevisionMeasurements
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.pdf.fidelity.compare import FidelityMeasurements
from odfa11y.pdf.structure.checks import PdfStructureMeasurements
from odfa11y.pdf.structure.links import PdfLinkMeasurements
from odfa11y.pdf.structure.marked_content import MarkedContentMeasurements
from odfa11y.pdf.validation import ValidationMeasurements
from odfa11y.plans import PlanHeader
from odfa11y.plans.contracts import decision_contract, file_contract
from odfa11y.remediate import RemediationResult
from odfa11y.remediate.catalogue import registered_kinds
from odfa11y.report import Finding, Report
from odfa11y.rules.registry import RULES
from odfa11y.run.record import RunRecord
from odfa11y.targets import Location


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
        RecordContract("audit", AuditResult),
        RecordContract("plan", PlanResult),
        RecordContract("remediation", RemediationResult),
        RecordContract("export", ExportResult),
        RecordContract("comparison", ComparisonResult),
        RecordContract("run", RunRecord),
        RecordContract("batch", BatchRecord),
        RecordContract("evidence-verification", VerificationResult),
        RecordContract("doctor", DoctorResult),
        RecordContract("report", Report),
        RecordContract("plan-file", file_contract(registered_kinds()), PlanHeader),
    )


def generated_schemas() -> dict[str, JsonObject]:
    """Generate published files from this registry and runtime annotations alone."""
    kinds = registered_kinds()
    measurements = (
        ExportContextMeasurements
        | DocumentMetadata
        | PackageMeasurements
        | ChartMeasurements
        | DatabaseMeasurements
        | FormulaMeasurements
        | ImageMeasurements
        | PageMeasurements
        | SpreadsheetMeasurements
        | TextStyleMeasurements
        | TextContentMeasurements
        | LanguageMeasurements
        | ListMeasurements
        | ReferenceMeasurements
        | TableMeasurements
        | VisibilityMeasurements
        | ReadingOrderMeasurements
        | RevisionMeasurements
        | PdfMeasurements
        | FidelityMeasurements
        | PdfLinkMeasurements
        | MarkedContentMeasurements
        | PdfStructureMeasurements
        | ValidationMeasurements
    )
    findings = reduce(
        or_,
        (
            mapping_contract(
                rule.id + "Finding",
                {
                    "rule_id": Literal.__getitem__((rule.id,)),
                    "message": str,
                    "location": Location | None,
                    "details": rule.details,
                    "severity": Literal.__getitem__((rule.severity.value,)),
                    "category": Literal.__getitem__((rule.category,)),
                },
            )
            for rule in RULES.values()
        ),
    )
    overrides: dict[object, object] = {
        Finding: findings,
        Report: Report[measurements],
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
