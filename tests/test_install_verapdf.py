# SPDX-License-Identifier: MPL-2.0
"""The veraPDF installer refuses a download that is not the pinned release."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.install_verapdf import configuration, release_url, verify_sha256


def test_the_release_url_groups_versions_by_series() -> None:
    assert release_url("1.30.2") == (
        "https://software.verapdf.org/releases/1.30/verapdf-greenfield-1.30.2-installer.zip"
    )


def test_a_matching_digest_is_accepted_and_any_other_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "verapdf.zip"
    archive.write_bytes(b"installer")
    verify_sha256(archive, hashlib.sha256(b"installer").hexdigest())
    verify_sha256(archive, hashlib.sha256(b"installer").hexdigest().upper())
    with pytest.raises(ValueError, match="expected"):
        verify_sha256(archive, "0" * 64)


def test_the_unattended_configuration_names_the_install_directory(tmp_path: Path) -> None:
    text = configuration(tmp_path / "verapdf")
    assert f"<installpath>{tmp_path / 'verapdf'}</installpath>" in text
    assert 'selected="true"' in text


def test_the_workflow_pins_the_release_this_tool_installs() -> None:
    workflow = (Path(__file__).parents[1] / ".github/workflows/checks.yml").read_text("utf-8")
    assert "tools/install_verapdf.py" in workflow
