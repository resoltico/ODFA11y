# SPDX-License-Identifier: MPL-2.0
"""Check shipped Markdown's local targets and GitHub-style heading anchors offline."""

from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from tests.fixtures.paths import REPOSITORY
from tools.source_inventory import source_files

LINK = re.compile(r"\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
DEFINITION = re.compile(r"^\s*\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def _prose(text: str) -> str:
    lines = []
    fence = ""
    for line in text.splitlines():
        if match := FENCE.match(line):
            token = match[1]
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append(line)
    return "\n".join(lines)


def _anchors(text: str) -> set[str]:
    anchors = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    counts: dict[str, int] = {}
    for line in _prose(text).splitlines():
        if not (match := HEADING.match(line)):
            continue
        title = re.sub(r"<[^>]+>", "", html.unescape(match[1])).lower()
        slug = "".join(
            character
            for character in title
            if character in " -_" or unicodedata.category(character)[0] in "LNM"
        )
        slug = slug.replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(slug + (f"-{count}" if count else ""))
    return anchors


def _links(text: str) -> list[str]:
    prose = re.sub(r"`+[^`\n]*`+", "", _prose(text))
    return [
        html.unescape(match[1] or match[2])
        for pattern in (LINK, DEFINITION)
        for match in pattern.finditer(prose)
    ]


def test_shipped_markdown_links_and_anchors_resolve() -> None:
    files = source_files(REPOSITORY)
    documents = {name: data.decode() for name, data in files.items() if name.endswith(".md")}
    errors = []
    for name, text in documents.items():
        for target in _links(text):
            reference = urlsplit(target)
            if reference.scheme or reference.netloc:
                continue
            path = (
                (REPOSITORY / name).parent / unquote(reference.path)
                if reference.path
                else REPOSITORY / name
            )
            path = path.resolve()
            if not path.exists():
                errors.append(f"{name}: missing {target}")
                continue
            anchor = unquote(reference.fragment)
            if not anchor or not path.is_file():
                continue
            if re.fullmatch(r"L\d+(?:-L\d+)?", anchor):
                continue
            relative = path.relative_to(REPOSITORY).as_posix()
            if anchor not in _anchors(documents.get(relative, "")):
                errors.append(f"{name}: missing anchor {target}")
    assert not errors, "\n".join(errors)
