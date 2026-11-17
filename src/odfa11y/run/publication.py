# SPDX-License-Identifier: AGPL-3.0-only
"""Publish only artifacts declared by completed run stages."""

from pathlib import Path

from odfa11y.evidence import (
    BinaryArtifact,
    BundleArtifact,
    JsonArtifact,
    Redactor,
    TextArtifact,
    XmlArtifact,
    write_bundle,
)
from odfa11y.progress import Step, step
from odfa11y.run.record import RunRecord
from odfa11y.run.review import render_review
from odfa11y.run.state import RunState


def publish_evidence(state: RunState, target: Path, record: RunRecord) -> None:
    """Publish typed artifacts without scans, diagnostic reparsing or finding-data lookups."""
    artifacts: dict[str, BundleArtifact] = {}
    if state.candidate_path is not None:
        artifacts[state.candidate_path.name] = BinaryArtifact(state.candidate_path)
    for artifact in (state.source_pdf, state.candidate_pdf):
        if artifact is not None:
            artifacts[artifact.path.name] = BinaryArtifact(artifact.path)
    if state.validation is not None:
        artifacts["verapdf.xml"] = XmlArtifact(state.validation.xml_root)
    if state.fidelity is not None:
        for image in state.fidelity.images:
            artifacts["diff/" + image.name] = BinaryArtifact(image)
    redactor = Redactor.for_locations({
        "profile": state.work / "profile",
        "work": state.work,
        "capture": state.source.path.parent,
        "source": state.source.identity.path.parent,
        "output": target,
    })
    artifacts["run.json"] = JsonArtifact(record.as_dict())
    artifacts["REVIEW.md"] = TextArtifact(render_review(record, redactor=redactor))
    with step(state.observer, Step.PUBLISH_EVIDENCE):
        write_bundle(target, artifacts, redactor)
