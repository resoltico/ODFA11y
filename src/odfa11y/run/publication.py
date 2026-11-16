# SPDX-License-Identifier: MPL-2.0
"""Publish pipeline evidence and report the actual publication outcome."""

lazy from pathlib import Path

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
from odfa11y.run.review import render_review
from odfa11y.safe_xml import parse_secure
lazy from odfa11y.progress import ProgressObserver
lazy from odfa11y.run.record import RunRecord


def publish_evidence(
    source: Path,
    target: Path,
    work: Path,
    record: RunRecord,
    observer: ProgressObserver | None,
) -> None:
    """Gather artifacts and publish a bundle without persisting progress events.

    Observers receive typed ProgressEvent values and must not raise. Publication failures
    and interruption retain their original exceptions and never report success.

    Raises
    ------
    OdfA11yError
        Evidence cannot be published safely.
    OSError
        Artifact collection or publication cannot complete.
    KeyboardInterrupt
        Publication is interrupted.

    """
    with step(observer, Step.PUBLISH_EVIDENCE):
        names = ("remediated" + source.suffix, "source.pdf", "remediated.pdf", "verapdf.xml")
        artifacts: dict[str, BundleArtifact] = {
            name: BinaryArtifact(work / name) for name in names if (work / name).is_file()
        }
        # The fidelity producer declares each difference image in its structured finding.
        for stage in record.stages:
            if stage.report is not None:
                for finding in stage.report.findings:
                    name = finding.details.get("diff_image")
                    if isinstance(name, str):
                        path = work / "diff" / name
                        if path.is_file():
                            artifacts["diff/" + name] = BinaryArtifact(path)
        if "verapdf.xml" in artifacts:
            artifacts["verapdf.xml"] = XmlArtifact(
                parse_secure((work / "verapdf.xml").read_bytes())
            )
        redactor = Redactor.for_locations({
            "profile": work / "profile",
            "work": work,
            "source": source.parent,
            "output": target,
        })
        artifacts["run.json"] = JsonArtifact(record.as_dict())
        artifacts["REVIEW.md"] = TextArtifact(render_review(record, redactor=redactor))
        write_bundle(target, artifacts, redactor)
