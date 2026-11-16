# SPDX-License-Identifier: MPL-2.0
"""Install the pinned LibreOffice input through one platform-aware CI path."""

import argparse
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

from tools.native_download import download

PINS = Path(__file__).with_name("native_versions.toml")
RELEASES = "https://download.documentfoundation.org/libreoffice/stable"


def install(destination: Path) -> Path:
    pins = tomllib.loads(PINS.read_text())["libreoffice"]
    version = pins["version"]
    destination.mkdir(parents=True)
    if sys.platform == "linux":
        archive = destination / "libreoffice.tar.gz"
        filename = f"LibreOffice_{version}_Linux_x86-64_deb.tar.gz"
        download(f"{RELEASES}/{version}/deb/x86_64/{filename}", pins["linux_sha256"], archive)
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination / "unpacked", filter="data")
        packages = sorted((destination / "unpacked").glob("*/DEBS/*.deb"))
        subprocess.run(["sudo", "apt-get", "update"], check=True, stdout=sys.stderr)  # noqa: S607  CI system package installation.
        subprocess.run(  # noqa: S603  Fixed CI qualification commands; no shell or document-controlled executable.
            [  # noqa: S607  Fixed CI qualification commands; no shell or document-controlled executable.
                "sudo",
                "apt-get",
                "install",
                "-y",
                "--no-install-recommends",
                *(str(path) for path in packages),
            ],
            check=True,
            stdout=sys.stderr,
        )
        return Path("/opt/libreoffice" + ".".join(version.split(".")[:2]) + "/program")
    if sys.platform == "darwin":
        archive = destination / "libreoffice.dmg"
        filename = f"LibreOffice_{version}_MacOS_aarch64.dmg"
        download(f"{RELEASES}/{version}/mac/aarch64/{filename}", pins["macos_sha256"], archive)
        mount = destination / "mount"
        subprocess.run(  # noqa: S603  Fixed CI qualification commands; no shell or document-controlled executable.
            [  # noqa: S607  Fixed CI qualification commands; no shell or document-controlled executable.
                "hdiutil",
                "attach",
                str(archive),
                "-mountpoint",
                str(mount),
                "-nobrowse",
                "-readonly",
            ],
            check=True,
            stdout=sys.stderr,
        )
        try:
            subprocess.run(  # noqa: S603  Fixed CI qualification commands; no shell or document-controlled executable.
                ["ditto", str(mount / "LibreOffice.app"), str(destination / "LibreOffice.app")],  # noqa: S607  Fixed CI qualification commands; no shell or document-controlled executable.
                check=True,
                stdout=sys.stderr,
            )
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True, stdout=sys.stderr)  # noqa: S603,S607  Detach the CI-owned mount.
        return destination / "LibreOffice.app/Contents/MacOS"
    if sys.platform == "win32":
        archive = destination / "libreoffice.msi"
        filename = f"LibreOffice_{version}_Win_x86-64.msi"
        download(f"{RELEASES}/{version}/win/x86_64/{filename}", pins["windows_sha256"], archive)
        result = subprocess.run(  # noqa: S603  Fixed CI qualification commands; no shell or document-controlled executable.
            ["msiexec.exe", "/i", str(archive), "/qn", "/norestart"],  # noqa: S607  Windows system installer.
            check=False,
        )
        if result.returncode not in {0, 3010}:
            message = f"LibreOffice installation failed with exit code {result.returncode}"
            raise RuntimeError(message)
        return Path("C:/Program Files/LibreOffice/program")
    message = "The pinned LibreOffice installer supports Linux, macOS and Windows runners"
    raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    sys.stdout.write(str(install(args.destination.resolve())) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
