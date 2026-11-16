# SPDX-License-Identifier: MPL-2.0
"""Download pinned native inputs and establish their exact byte identity."""

import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

TIMEOUT_SECONDS = 300


def verify_sha256(path: Path, expected: str) -> None:
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected.lower():
        message = f"{path.name} has SHA-256 {actual}, expected {expected}"
        raise ValueError(message)


def download(url: str, sha256: str, destination: Path) -> None:
    sys.stderr.write(f"Downloading {destination.name} from {url}\n")
    with (
        urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response,  # noqa: S310  Vendor HTTPS endpoints with independently pinned hashes.
        destination.open("wb") as stream,
    ):
        sys.stderr.write(f"Connected; receiving {destination.name}\n")
        shutil.copyfileobj(response, stream)
    sys.stderr.write(f"Transfer complete; verifying {destination.name}\n")
    verify_sha256(destination, sha256)
    sys.stderr.write(f"Verified {destination.name}\n")
