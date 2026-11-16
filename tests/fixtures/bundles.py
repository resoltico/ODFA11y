# SPDX-License-Identifier: AGPL-3.0-only
"""Author run-owned metadata explicitly when testing the generic evidence writer."""

import json
from collections.abc import Mapping
from pathlib import Path

from odfa11y.errors import OutputOccupied
from odfa11y.evidence import (
    BinaryArtifact,
    BundleArtifact,
    JsonArtifact,
    Redactor,
    TextArtifact,
    XmlArtifact,
    write_bundle,
)
from odfa11y.run.record import RunRecord
from odfa11y.run.review import render_review
from odfa11y.safe_xml import parse_secure


def write_run_bundle(
    directory: str | Path,
    record: RunRecord,
    artifacts: Mapping[str, Path],
    redactor: Redactor,
    *,
    diagnostics: set[str] | frozenset[str] = frozenset(),
) -> None:
    files: dict[str, BundleArtifact] = {}
    for name, path in artifacts.items():
        if name.casefold() in {"run.json", "review.md", "manifest.json"}:
            message = "The run producer owns its record and review filenames"
            raise OutputOccupied(message)
        if name not in diagnostics:
            files[name] = BinaryArtifact(path)
        elif path.suffix == ".xml":
            files[name] = XmlArtifact(parse_secure(path.read_bytes()))
        elif path.suffix == ".json":
            files[name] = JsonArtifact(json.loads(path.read_text()))
        else:
            files[name] = TextArtifact(path.read_text())
    files["run.json"] = JsonArtifact(record.as_dict())
    files["REVIEW.md"] = TextArtifact(render_review(record, redactor=redactor))
    write_bundle(directory, files, redactor)
