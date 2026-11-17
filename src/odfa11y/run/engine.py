# SPDX-License-Identifier: AGPL-3.0-only
"""Execute the stage table and derive an immutable record from completed outcomes."""

from dataclasses import replace
from pathlib import Path

from odfa11y.native.tools import Toolchain
from odfa11y.remediate.result import PublicationState
from odfa11y.run.publication import publish_evidence
from odfa11y.run.record import RunRecord
from odfa11y.run.stages import STAGES, run_stage
from odfa11y.run.state import RunState


def execute(state: RunState, target: Path) -> RunRecord:
    detection = state.document.detection
    stages = []
    for spec in STAGES:
        state, result = run_stage(spec, state)
        stages.append(result)
    if state.candidate_path is not None:
        stages = [
            replace(
                stage,
                remediation=replace(
                    stage.remediation,
                    publication=PublicationState.PUBLISHED,
                    _destination=target / state.candidate_path.name,
                ),
            )
            if stage.remediation is not None
            else stage
            for stage in stages
        ]
    record = RunRecord(
        document=detection,
        source_name=state.source.identity.name,
        source_sha256=state.source.digest,
        fidelity_policy=state.plan.fidelity,
        profile=state.profile,
        stages=tuple(stages),
        fonts={"source": state.source_fonts, "remediated": state.candidate_fonts},
        plan=state.plan.header,
        decisions=state.plan.decisions,
        toolchain=Toolchain(
            state.tools.libreoffice.identity if state.tools.libreoffice else None,
            state.tools.verapdf.identity if state.tools.verapdf else None,
        ),
        human_review=tuple(
            item
            for item in state.family.review_items
            if state.source_report is not None and item.key in state.source_report.review_topics
        ),
    )
    publish_evidence(state, target, record)
    return record
