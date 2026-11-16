# SPDX-License-Identifier: MPL-2.0
"""Rebuild distributions and verify an installed wheel outside the checkout."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

from tools.build_distributions import build

ROOT = Path(__file__).resolve().parents[1]
SMOKE = """import hashlib
import importlib.metadata
import json
import runpy
import sys
from pathlib import Path
import odfa11y
import odfa11y.odf as odf

expected = json.loads(Path(sys.argv[1]).read_text())
package = importlib.metadata.distribution(expected["name"])
assert Path(odfa11y.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert package.version == expected["version"] == odfa11y.__version__
assert package.metadata["Requires-Python"] == expected["requires-python"]
assert package.metadata["License-Expression"] == expected["license"]
assert any(str(name).endswith("odfa11y/py.typed") for name in package.files)
for name, details in odf.provenance().items():
    path = package.locate_file("odfa11y/odf/schemas/" + name)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == details["sha256"]
source = Path("source.fodt")
source.write_text(\'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.4" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:meta><dc:title>Wheel qualification</dc:title><dc:language>en-GB</dc:language></office:meta>
 <office:styles><style:default-style style:family="paragraph">
 <style:text-properties fo:language="en" fo:country="GB"/>
 </style:default-style></office:styles>
 <office:body><office:text><text:h text:outline-level="1">Qualification</text:h>
 <text:p>Invented source text.</text:p></office:text></office:body>
</office:document>\''')
original = source.read_bytes()
examples = runpy.run_path(str(Path("core_examples.py").resolve()))
reports = examples["inspect_source"](source.resolve(), Path("work").resolve())
assert len(reports) == 2
assert all(report.error_count == 0 for report in reports)
assert source.read_bytes() == original
assert Path("work/reviewed.fodt").is_file()
assert odf.validate(odf.OdfDocument.open("work/reviewed.fodt")).count == 0
assert not any(name == "odfa11y.cli" or name.startswith("odfa11y.cli.") for name in sys.modules)
print("Installed-wheel provenance and public examples passed.")
"""


def _run(arguments: list[str], cwd: Path) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)  # noqa: S603  Fixed qualification commands, no shell.


def _require_reproducible(expected: dict[str, str], actual: dict[str, str]) -> None:
    if actual != expected:
        message = "Distributions rebuilt from the source archive differ byte-for-byte"
        raise ValueError(message)


def qualify(directory: Path) -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    artifacts = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for pattern in ("*.whl", "*.tar.gz")
        for path in directory.glob(pattern)
    }
    if len(tuple(directory.glob("*.whl"))) != 1 or len(tuple(directory.glob("*.tar.gz"))) != 1:
        message = "Qualification requires the checked wheel and source archive"
        raise ValueError(message)
    work = Path(tempfile.mkdtemp(prefix="odfa11y-qualification-"))
    try:
        source_root = work / "source"
        source_root.mkdir()
        with tarfile.open(next(directory.glob("*.tar.gz"))) as archive:
            archive.extractall(source_root, filter="data")
        source = next(source_root.iterdir())
        rebuild = work / "rebuilt"
        build(source, rebuild)
        actual = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for pattern in ("*.whl", "*.tar.gz")
            for path in rebuild.glob(pattern)
        }
        _require_reproducible(artifacts, actual)
        environment = work / "wheel-env"
        _run(["uv", "venv", "--python", sys.executable, str(environment)], work)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        requirements = work / "runtime-requirements.txt"
        _run(
            [
                "uv",
                "export",
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(requirements),
            ],
            ROOT,
        )
        _run(
            ["uv", "pip", "sync", "--python", str(python), "--require-hashes", str(requirements)],
            work,
        )
        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                str(next(directory.glob("*.whl"))),
            ],
            work,
        )
        smoke = work / "installed"
        smoke.mkdir()
        shutil.copyfile(ROOT / "tools/core_examples.py", smoke / "core_examples.py")
        (smoke / "expected.json").write_text(json.dumps(project))
        (smoke / "smoke.py").write_text(SMOKE)
        _run([str(python), "-I", str(smoke / "smoke.py"), str(smoke / "expected.json")], smoke)
    except BaseException:
        sys.stderr.write(f"Qualification evidence retained at {work}\n")
        raise
    else:
        shutil.rmtree(work)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    qualify(args.directory.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
