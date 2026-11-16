# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for publication identity."""

import hashlib
import json
lazy from collections.abc import Callable
lazy from pathlib import Path

from lxml import etree

from odfa11y.application.tools import Tools
from odfa11y.evidence import check_bundle
from odfa11y.odf import OdfDocument, PackageStorage
from odfa11y.plans.fidelity import Pagination
from odfa11y.status import Profile
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.runs import RunSettings, execute
from tests.fixtures.writer import make_minimal_odt


def test_native_published_artifact_syntax_content_and_identity(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    package = PackageStorage(source)
    authored = str(tmp_path / "authored-file").encode()
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"Body paragraph.", authored)
    )
    package.save(source)
    target = tmp_path / "bundle"
    result = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        target,
        RunSettings(
            tools=Tools(
                soffice=external_tool("soffice", "libreoffice"), verapdf=external_tool("verapdf")
            ),
            profile=Profile.parse("production"),
        ),
    )
    assert result.passed, result.as_dict()
    delivered = OdfDocument.open(target / "remediated.odt")
    assert authored in delivered.storage.read("content.xml")
    assert (target / "remediated.odt").read_bytes() == source.read_bytes()
    etree.parse(target / "verapdf.xml")
    published = json.loads((target / "run.json").read_text())
    manifest = json.loads((target / "manifest.json").read_text())["files"]
    assert "outputs" not in published
    for name, digest in manifest.items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
    for name, digest in json.loads((target / "manifest.json").read_text())["files"].items():
        assert digest == manifest[name]
    assert check_bundle(target) == []
