# SPDX-License-Identifier: AGPL-3.0-only
"""Rebuild selected invented corpus artifacts into a new directory for review."""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import tomllib
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

from odfa11y.application.tools import Tools
from odfa11y.native.process import run_bounded
from odfa11y.native.tools import LibreOffice
from odfa11y.odf import NS, OdfDocument, PackageStorage, Part, qn, validate

ROOT = Path(__file__).resolve().parents[1] / "tests/corpus"
TIMEOUT = 120
LIBRARY = "http://openoffice.org/2000/library"
SCRIPT = "http://openoffice.org/2000/script"


def _convert(source: Path, destination: Path, format_filter: str, office: LibreOffice) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="odfa11y-corpus-convert-") as temporary:
        work = Path(temporary)
        result = run_bounded(
            [
                office.executable,
                f"-env:UserInstallation={(work / 'profile').as_uri()}",
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                "--convert-to",
                destination.suffix[1:] + ":" + format_filter,
                "--outdir",
                str(work / "output"),
                str(source),
            ],
            timeout=TIMEOUT,
        )
        produced = work / "output" / source.with_suffix(destination.suffix).name
        if result.returncode or not produced.is_file():
            message = "LibreOffice did not produce the selected corpus conversion: " + result.stderr
            raise RuntimeError(message)
        shutil.copyfile(produced, destination)


def _profile(profile: Path, module: Path, output: Path) -> None:
    """Install only the repository's trusted fixture macro in a disposable user profile."""
    standard = profile / "user/basic/CorpusAuthoring"
    standard.mkdir(parents=True, exist_ok=True)
    source = module.read_text().replace(
        'Environ("ODFA11Y_FIXTURE_ROOT")', '"' + str(output).replace('"', '""') + '"'
    )
    (standard / "Author.xba").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE script:module"
        ' PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">\n'
        f'<script:module xmlns:script="{SCRIPT}" script:name="Author" '
        f'script:language="StarBasic">{escape(source)}</script:module>'
    )
    (standard / "script.xlb").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE library:library"
        ' PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "library.dtd">\n'
        f'<library:library xmlns:library="{LIBRARY}" library:name="CorpusAuthoring" '
        'library:readonly="false" library:passwordprotected="false">'
        '<library:element library:name="Author"/></library:library>'
    )
    (profile / "user/basic/script.xlc").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE library:libraries"
        ' PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "libraries.dtd">\n'
        f'<library:libraries xmlns:library="{LIBRARY}" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<library:library library:name="Standard" library:link="false"/>'
        '<library:library library:name="CorpusAuthoring" '
        f'xlink:href="{(standard / "script.xlb").as_uri()}" '
        'xlink:type="simple" library:link="true" library:readonly="false"/></library:libraries>'
    )
    (standard / "dialog.xlb").write_text(
        f'<library:library xmlns:library="{LIBRARY}" library:name="CorpusAuthoring" '
        'library:readonly="false" library:passwordprotected="false"/>'
    )
    (profile / "user/basic/dialog.xlc").write_text(
        f'<library:libraries xmlns:library="{LIBRARY}" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<library:library library:name="Standard" library:link="false"/>'
        '<library:library library:name="CorpusAuthoring" '
        f'xlink:href="{(standard / "dialog.xlb").as_uri()}" '
        'xlink:type="simple" library:link="true" library:readonly="false"/></library:libraries>'
    )
    registry = profile / "user/registrymodifications.xcu"
    settings = etree.parse(registry).getroot()
    oor = "http://openoffice.org/2001/registry"
    for path, name, value in (
        ("/org.openoffice.Office.Common/Security/Scripting", "MacroSecurityLevel", "0"),
        ("/org.openoffice.Office.Common/Save/ODF", "DefaultVersion", "12"),
    ):
        item = next((node for node in settings if node.get(f"{{{oor}}}path") == path), None)
        if item is None:
            item = etree.SubElement(settings, "item", {f"{{{oor}}}path": path})
        prop = next((node for node in item if node.get(f"{{{oor}}}name") == name), None)
        if prop is None:
            prop = etree.SubElement(item, "prop", {f"{{{oor}}}name": name, f"{{{oor}}}op": "fuse"})
        for node in tuple(prop):
            prop.remove(node)
        etree.SubElement(prop, "value").text = value
    registry.write_bytes(etree.tostring(settings, xml_declaration=True, encoding="UTF-8"))


def _macro(name: str, output: Path, office: LibreOffice) -> None:
    with tempfile.TemporaryDirectory(prefix="odfa11y-corpus-macro-") as temporary:
        profile = Path(temporary) / "profile"
        initialized = run_bounded(
            [
                office.executable,
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--terminate_after_init",
            ],
            timeout=TIMEOUT,
        )
        if initialized.returncode:
            message = "LibreOffice could not initialize the disposable authoring profile"
            raise RuntimeError(message)
        _profile(profile, ROOT / "families/sources" / name, output)
        result = run_bounded(
            [
                office.executable,
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                "macro:///CorpusAuthoring.Author.Main",
            ],
            timeout=TIMEOUT,
        )
        if result.returncode:
            message = "Trusted corpus authoring macro failed: " + result.stderr
            raise RuntimeError(message)


def _package(
    destination: Path, media_type: str, parts: dict[str, bytes], media_types: dict[str, str]
) -> None:
    manifest = etree.Element(qn("manifest", "manifest"), nsmap={"manifest": NS["manifest"]})
    manifest.set(qn("manifest", "version"), "1.4")
    for name, media in [("/", media_type), *media_types.items()]:
        etree.SubElement(
            manifest,
            qn("manifest", "file-entry"),
            {
                qn("manifest", "full-path"): name,
                qn("manifest", "media-type"): media,
            },
        )
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", media_type, compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/manifest.xml",
            etree.tostring(manifest, xml_declaration=True, encoding="UTF-8"),
        )
        for name, content in parts.items():
            archive.writestr(name, content)


def _chart(source: Path, destination: Path) -> None:
    document = OdfDocument.open(source)
    entries = document.tree(Part.MANIFEST).findall("manifest:file-entry", NS)
    prefixes = [
        node.get(qn("manifest", "full-path"))
        for node in entries
        if node.get(qn("manifest", "media-type")) == "application/vnd.oasis.opendocument.chart"
    ]
    if len(prefixes) != 1 or prefixes[0] is None:
        message = "The trusted Calc source must contain one chart subdocument"
        raise ValueError(message)
    prefix = prefixes[0].rstrip("/") + "/"
    parts = {
        name: document.storage.read(prefix + name)
        for name in ("content.xml", "styles.xml", "meta.xml")
        if document.storage.has(prefix + name)
    }
    _package(
        destination,
        "application/vnd.oasis.opendocument.chart",
        parts,
        dict.fromkeys(parts, "text/xml"),
    )


def _image(source: Path, destination: Path) -> None:
    document = OdfDocument.open(source)
    content = deepcopy(document.tree(Part.CONTENT))
    body = content.find("office:body", NS)
    frame = content.find(".//draw:frame[draw:image]", NS)
    if body is None or frame is None:
        message = "The trusted Draw source must contain an image frame"
        raise ValueError(message)
    image = etree.Element(qn("office", "image"))
    image.append(deepcopy(frame))
    for child in tuple(body):
        body.remove(child)
    body.append(image)
    parts = {"content.xml": etree.tostring(content, xml_declaration=True, encoding="UTF-8")}
    if not isinstance(document.storage, PackageStorage):
        message = "Image assembly requires a native Draw package"
        raise TypeError(message)
    for name in document.storage.member_names():
        if name in {"styles.xml", "meta.xml"} or name.startswith("Pictures/"):
            parts[name] = document.storage.read(name)
    media_types = {
        node.get(qn("manifest", "full-path"), ""): node.get(qn("manifest", "media-type"), "")
        for node in document.tree(Part.MANIFEST).findall("manifest:file-entry", NS)
    }
    _package(
        destination,
        "application/vnd.oasis.opendocument.image",
        parts,
        {name: media_types.get(name, "text/xml") for name in parts},
    )


def _families(selected: set[str], output: Path, office: LibreOffice) -> None:
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "families/sources/fruit.svg", output / "fruit.svg")
    if selected & {"presentation", "drawing", "image"}:
        _macro("page-documents.bas", output, office)
    for family, module in (
        ("formula", "formula-document.bas"),
        ("database", "database-document.bas"),
    ):
        if family in selected:
            _macro(module, output, office)
    if "chart" in selected:
        _macro("chart-document.bas", output, office)
        _chart(output / "fruit-chart-source.ods", output / "fruit-chart.odc")
    if "image" in selected:
        _image(output / "fruit-drawing.odg", output / "fruit-image.odi")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="New output directory; stored expectations are never updated."
    )
    parser.add_argument("--family", help="Select one family from the manifest.")
    parser.add_argument("--purpose", help="Select one recorded purpose.")
    parser.add_argument("--soffice", type=Path)
    args = parser.parse_args()
    manifest = tomllib.loads((ROOT / "manifest.toml").read_text())
    entries = [
        entry
        for entry in manifest["document"]
        if (args.family is None or entry["family"] == args.family)
        and (args.purpose is None or args.purpose in entry["purposes"])
    ]
    if not entries:
        parser.error("No corpus entries match the selected family and purpose")
    office = Tools(soffice=args.soffice).resolve(libreoffice=True).libreoffice
    if office is None:
        message = "Corpus preparation did not establish LibreOffice"
        raise ValueError(message)
    args.output.mkdir(parents=True)
    families = {entry["family"] for entry in entries if entry["builder"] == "native-services"}
    if families:
        _families(families, args.output / "families", office)
    for entry in entries:
        destination = args.output / entry["file"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if entry["builder"] == "copy":
            shutil.copyfile(ROOT / entry["file"], destination)
        elif entry["builder"] == "convert":
            _convert(ROOT / entry["source"], destination, entry["filter"], office)
        elif not destination.is_file():
            message = "Trusted native authoring did not produce " + entry["file"]
            raise RuntimeError(message)
    records = [
        {
            "file": entry["file"],
            "sha256": hashlib.sha256((args.output / entry["file"]).read_bytes()).hexdigest(),
            "schema_violations": validate(OdfDocument.open(args.output / entry["file"])).count,
        }
        for entry in entries
    ]
    sys.stdout.write(
        json.dumps({"producer": office.identity.version, "documents": records}, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
