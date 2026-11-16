# SPDX-License-Identifier: AGPL-3.0-only
"""Plan application use case."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from odfa11y.application.io_errors import translate_io
from odfa11y.audit import prepare_plan
from odfa11y.contracts import JsonObject, JsonProperty, record_dict
from odfa11y.plans import Plan
from odfa11y.remediate.catalogue import load_plan
from odfa11y.report import Report, exit_status
from odfa11y.status import ExitStatus


@dataclass(frozen=True, slots=True)
class PlanResult:
    """A source report and its bound disabled-answer template when planning is possible."""

    schema_version: Literal[1] = field(default=1, init=False)

    report: Report
    template: str | None

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Whether a reviewable plan was prepared."""
        return ExitStatus.PASSED if self.template is not None else exit_status([self.report])

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@translate_io
def plan(
    source: str | Path, *, from_plan: Plan | str | Path | None = None, include_all: bool = False
) -> PlanResult:
    """Prepare source-bound human questions without changing the document."""
    previous = (
        (from_plan if isinstance(from_plan, Plan) else load_plan(from_plan))
        if from_plan is not None
        else None
    )
    report, template = prepare_plan(source, previous=previous, include_all=include_all)
    return PlanResult(report, template)
