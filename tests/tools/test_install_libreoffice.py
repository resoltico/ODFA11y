# SPDX-License-Identifier: MPL-2.0
"""A checked vendor input must precede native installation on every platform."""

import hashlib
import io
import subprocess
from pathlib import Path

import pytest

from tools import install_libreoffice as installer
from tools import native_download
from tools.native_download import TIMEOUT_SECONDS


def test_bad_download_never_reaches_the_system_installer(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def reject(*args):
        message = "Pinned digest mismatch"
        raise ValueError(message)

    def invoke(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(installer, "download", reject)
    monkeypatch.setattr(installer.subprocess, "run", invoke)
    with pytest.raises(ValueError, match="Pinned digest"):
        installer.install(tmp_path / "application")
    assert not calls


@pytest.mark.parametrize("status", [0, 3010, 1])
def test_windows_installer_accepts_only_success_and_reboot_success(
    tmp_path: Path, monkeypatch, status: int
) -> None:
    operations = []

    def fetch(url, digest, destination):
        assert url.startswith("https://download.documentfoundation.org/libreoffice/stable/")
        assert len(digest) == 64
        destination.write_bytes(b"Checked fixture input")
        operations.append("verified")

    def invoke(command, **kwargs):
        assert operations == ["verified"]
        assert command[0] == "msiexec.exe"
        operations.append("installed")
        return subprocess.CompletedProcess(command, status)

    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(installer, "download", fetch)
    monkeypatch.setattr(installer.subprocess, "run", invoke)
    if status in {0, 3010}:
        assert installer.install(tmp_path / "application") == Path(
            "C:/Program Files/LibreOffice/program"
        )
    else:
        with pytest.raises(RuntimeError, match="exit code 1"):
            installer.install(tmp_path / "application")
    assert operations == ["verified", "installed"]


def test_vendor_download_passes_a_finite_timeout_and_verifies_received_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    content = b"Pinned vendor payload"
    observed = []

    def response(url, *, timeout):
        observed.append(timeout)
        return io.BytesIO(content)

    monkeypatch.setattr(native_download.urllib.request, "urlopen", response)
    target = tmp_path / "installer"
    native_download.download(
        "https://example.test/installer", hashlib.sha256(content).hexdigest(), target
    )
    assert observed == [TIMEOUT_SECONDS]
    assert 0 < observed[0] < float("inf")
    assert target.read_bytes() == content
