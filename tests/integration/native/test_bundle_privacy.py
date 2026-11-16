# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for bundle privacy."""

import re
lazy from collections.abc import Callable
lazy from pathlib import Path

from lxml import etree

from odfa11y.application.tools import Tools
from odfa11y.status import Profile
from tests.evidence.test_bundle_privacy import assert_path_free, run, workspace
from tests.fixtures.runs import RunSettings


def test_raw_tool_reports_of_a_real_run_are_not_leaked(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    directory = workspace(tmp_path)
    options = RunSettings(
        tools=Tools(
            soffice=external_tool("soffice", "libreoffice"), verapdf=external_tool("verapdf")
        ),
        profile=Profile.parse("production"),
    )
    bundle = run(directory, options)
    assert_path_free(bundle, tmp_path)
    root = etree.parse(bundle / "verapdf.xml").getroot()
    report = " ".join(
        value for node in root.iter() for value in [node.text or "", *node.attrib.values()]
    )
    # The tool echoes the path with the platform's separators; a spelling the redactor cannot
    # know (a Windows 8.3 short name) collapses to <path> instead of <work>.
    assert re.search(r"<(work|path)>[\\/]remediated\.pdf", report)
