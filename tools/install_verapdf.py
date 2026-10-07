# SPDX-License-Identifier: MPL-2.0
"""Install the pinned veraPDF release on any runner and print the directory to put on PATH."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

DOWNLOAD = (
    "https://software.verapdf.org/releases/{series}/verapdf-greenfield-{version}-installer.zip"
)
INSTALLER = "verapdf-greenfield-{version}/verapdf-izpack-installer-{version}.jar"
TIMEOUT_SECONDS = 300
CONFIGURATION = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<AutomatedInstallation langpack="eng">
  <com.izforge.izpack.panels.htmlhello.HTMLHelloPanel id="welcome"/>
  <com.izforge.izpack.panels.target.TargetPanel id="install_dir">
    <installpath>{install_dir}</installpath>
  </com.izforge.izpack.panels.target.TargetPanel>
  <com.izforge.izpack.panels.packs.PacksPanel id="sdk_pack_select">
    <pack index="0" name="veraPDF Runtime" selected="true"/>
  </com.izforge.izpack.panels.packs.PacksPanel>
  <com.izforge.izpack.panels.install.InstallPanel id="install"/>
  <com.izforge.izpack.panels.finish.FinishPanel id="finish"/>
</AutomatedInstallation>
"""


def release_url(version: str) -> str:
    """Name the download address of a veraPDF release.

    Returns
    -------
    str
        The installer archive's HTTPS address; releases are grouped by major.minor series.

    """
    return DOWNLOAD.format(series=version.rpartition(".")[0], version=version)


def verify_sha256(path: Path, expected: str) -> None:
    """Refuse a file whose SHA-256 differs from the pinned digest.

    Raises
    ------
    ValueError
        The digest differs.

    """
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected.lower():
        msg = f"{path.name} has SHA-256 {actual}, expected {expected}"
        raise ValueError(msg)


def configuration(install_dir: Path) -> str:
    """Build the unattended installer configuration.

    Returns
    -------
    str
        The IzPack automated-installation XML for the given directory.

    """
    return CONFIGURATION.format(install_dir=escape(str(install_dir)))


def install(version: str, sha256: str, destination: Path) -> Path:
    """Download, verify and install veraPDF into ``destination``.

    Returns
    -------
    Path
        The installation directory, which holds the ``verapdf`` launcher.

    """
    with tempfile.TemporaryDirectory(prefix="odfa11y-verapdf-") as scratch:
        work = Path(scratch)
        archive = work / "verapdf.zip"
        with urllib.request.urlopen(release_url(version), timeout=TIMEOUT_SECONDS) as response:
            archive.write_bytes(response.read())
        verify_sha256(archive, sha256)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(work / "installer")
        (work / "install.xml").write_text(configuration(destination), encoding="utf-8")
        jar = work / "installer" / INSTALLER.format(version=version)
        subprocess.run(
            ["java", "-jar", str(jar), str(work / "install.xml")],
            check=True,
            timeout=TIMEOUT_SECONDS,
        )
    return destination


def main() -> int:
    """Install veraPDF and print its directory.

    Returns
    -------
    int
        Zero on success.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("sha256")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    sys.stdout.write(f"{install(args.version, args.sha256, args.destination)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
