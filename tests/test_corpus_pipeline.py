# SPDX-License-Identifier: MPL-2.0
"""Real LibreOffice runs the assurance pipeline on documents Writer itself authored."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.evidence import check_bundle
from odfa11y.families.text import AltText, LinkifyAddresses, SetAltText
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import STAGE_NAMES, PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata

from .corpus_manifest import CORPUS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.adapter import Operation

# Each plan resolves the document's findings that would otherwise fail the audit gate.
PIPELINE_RUNS: dict[str, list[Operation]] = {
    "links.odt": [LinkifyAddresses()],
    "images-undescribed.fodt": [SetAltText({"Image1": AltText("Red square")})],
    "header-footer.fodt": [],
}


@pytest.mark.integration
@pytest.mark.parametrize("name", PIPELINE_RUNS)
def test_the_pipeline_runs_to_verified_evidence_on_a_writer_document(
    name: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    plan = [SetMetadata(title="Corpus document", language="en-US"), *PIPELINE_RUNS[name]]
    record = run_pipeline(
        CORPUS / name, plan, FidelityPolicy(), tmp_path / "out", PipelineOptions(soffice=soffice)
    )
    stages = {stage.name: stage.status for stage in record.stages}
    assert tuple(stages) == STAGE_NAMES
    assert stages["export-remediated"] == stages["fidelity"] == "passed", stages
    assert "failed" not in stages.values(), stages
    assert check_bundle(tmp_path / "out") == []
