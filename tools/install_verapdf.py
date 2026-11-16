# SPDX-License-Identifier: AGPL-3.0-only
"""Install the pinned veraPDF release on any runner and print the directory to put on PATH."""

import argparse
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from tools.native_download import download

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
        download(release_url(version), sha256, archive)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(work / "installer")
        (work / "install.xml").write_text(configuration(destination), encoding="utf-8")
        jar = work / "installer" / INSTALLER.format(version=version)
        subprocess.run(  # noqa: S603  Arguments select a local tool without a shell.
            ["java", "-jar", str(jar), str(work / "install.xml")],  # noqa: S607  System tool is resolved through PATH.
            check=True,
            stdout=sys.stderr,
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
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    pins = tomllib.loads(Path(__file__).with_name("native_versions.toml").read_text())["verapdf"]
    sys.stdout.write(f"{install(pins['version'], pins['sha256'], args.destination)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
