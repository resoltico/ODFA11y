# SPDX-License-Identifier: MPL-2.0
"""Publish only declared binary, structured and textual evidence artifacts."""

import json
import shutil
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from lxml import etree

from odfa11y.contracts import JsonObject
from odfa11y.errors import OutputOccupied
from odfa11y.evidence.manifest import write_manifest
from odfa11y.evidence.paths import unsafe_reason
from odfa11y.evidence.redact import Redactor
from odfa11y.publish import (
    publish_directory,
    publish_file,
    require_empty_directory,
    staging_sibling,
)


@dataclass(frozen=True, slots=True)
class BinaryArtifact:
    source: Path


@dataclass(frozen=True, slots=True)
class JsonArtifact:
    value: JsonObject


@dataclass(frozen=True, slots=True)
class TextArtifact:
    value: str


@dataclass(frozen=True, slots=True)
class XmlArtifact:
    root: etree._Element


type BundleArtifact = BinaryArtifact | JsonArtifact | TextArtifact | XmlArtifact


def require_free_directory(directory: Path) -> None:
    require_empty_directory(directory)


def write_bundle(
    directory: str | Path, artifacts: Mapping[str, BundleArtifact], redactor: Redactor
) -> None:
    target = Path(directory)
    require_empty_directory(target)
    names = tuple(artifacts)
    if len({name.casefold() for name in names}) != len(names):
        message = "Evidence artifact names collide on a case-insensitive file system"
        raise OutputOccupied(message)
    for name in names:
        if reason := unsafe_reason(name):
            message = f"Unsafe evidence artifact name {name!r}: {reason}"
            raise OutputOccupied(message)
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = staging_sibling(target)
    staged.mkdir()
    try:
        for name, artifact in artifacts.items():
            publish_file(
                staged / name,
                lambda stream, artifact=artifact: _write_artifact(artifact, stream, redactor),
            )
        write_manifest(staged, names)
        publish_directory(staged, target)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _write_artifact(artifact: BundleArtifact, stream: BinaryIO, redactor: Redactor) -> None:
    match artifact:
        case BinaryArtifact(source=source):
            with source.open("rb") as content:
                shutil.copyfileobj(content, stream)
        case JsonArtifact(value=value):
            encoded = (
                json.dumps(redactor.record(value), indent=2, sort_keys=True, ensure_ascii=False)
                + "\n"
            )
            stream.write(encoded.encode("utf-8"))
        case TextArtifact(value=value):
            stream.write(redactor.text(value).encode("utf-8"))
        case XmlArtifact(root=root):
            root = deepcopy(root)
            for node in root.iter():
                if node.text:
                    node.text = redactor.text(node.text)
                if node.tail:
                    node.tail = redactor.text(node.tail)
                for name, value in node.attrib.items():
                    node.set(name, redactor.text(value))
            stream.write(etree.tostring(root, encoding="utf-8", xml_declaration=True))
