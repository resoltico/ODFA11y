# SPDX-License-Identifier: MPL-2.0
"""Apply explicit, text-preserving remediation choices to an ODT document."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from odfa11y.odf import (
    NS,
    ODT_MIMETYPE,
    OdtPackage,
    StyleCatalog,
    is_empty_paragraph,
    qn,
    select_elements,
    text_is_preserved,
    visible_text_snapshot,
)

from .links import linkify_plain_addresses
from .metadata import set_default_style_language, set_metadata_text
from .models import AltText, RemediationOptions, RemediationResult
from .spacing import normalize_paragraph_spacing

__all__ = [
    "AltText",
    "RemediationOptions",
    "RemediationResult",
    "apply_alt_text",
    "apply_table_headers",
    "linkify_plain_addresses",
    "normalize_paragraph_spacing",
    "remediate_odt",
    "remove_empty_spacer_paragraphs",
]


def remediate_odt(
    source: str | Path,
    destination: str | Path,
    *,
    options: RemediationOptions,
) -> RemediationResult:
    """Apply explicit structural fixes while preserving visible text.

    Returns
    -------
    RemediationResult
        The saved paths and a list of applied changes.

    Raises
    ------
    ValueError
        Structural changes alter visible document text.

    """
    source = Path(source)
    destination = Path(destination)
    package = OdtPackage(source)
    before_text = visible_text_snapshot(package)
    changes: list[str] = []

    content = package.parse_xml("content.xml")
    styles = package.parse_xml("styles.xml")
    meta = package.parse_xml("meta.xml")
    manifest = package.parse_xml("META-INF/manifest.xml")
    settings = package.parse_xml("settings.xml") if package.has("settings.xml") else None

    _set_version_declarations(
        [content, styles, meta, *([settings] if settings is not None else [])],
        manifest,
        options.target_version,
        changes,
    )
    _apply_document_metadata(meta, styles, options, changes)

    if options.linkify_plain_addresses:
        count = linkify_plain_addresses(content)
        if count:
            changes.append(f"Converted {count} plain URL/email occurrence(s) to ODF hyperlinks.")

    if options.alt_text:
        count = apply_alt_text(content, options.alt_text)
        if count:
            changes.append(f"Applied accessible title/description to {count} graphic frame(s).")

    if options.table_header_rows:
        count = apply_table_headers(content, options.table_header_rows)
        if count:
            changes.append(f"Marked header rows semantically in {count} table(s).")

    removed_spacers = _remove_spacers(package, content, options, changes)

    package.write_xml("content.xml", content)
    package.write_xml("styles.xml", styles)
    package.write_xml("meta.xml", meta)
    package.write_xml("META-INF/manifest.xml", manifest)
    if settings is not None:
        package.write_xml("settings.xml", settings)

    after_text = visible_text_snapshot(package)
    if not text_is_preserved(before_text, after_text, removed_empty_blocks=removed_spacers):
        msg = (
            "Visible document text changed during a structure-only remediation. "
            "Aborting rather than silently altering content."
        )
        raise ValueError(msg)

    package.save(destination)
    return RemediationResult(source=source, destination=destination, changes=changes)


def apply_alt_text(tree: etree._ElementTree, mapping: dict[str, AltText]) -> int:
    """Apply accessible graphic text matched by frame name or image path.

    Returns
    -------
    int
        The number of matched graphic frames.

    """
    changed = 0
    for frame in select_elements(tree, "//draw:frame"):
        image = frame.find("draw:image", NS)
        href = image.get(qn("xlink", "href")) if image is not None else None
        name = frame.get(qn("draw", "name"))
        keys = [key for key in (name, href, Path(href).name if href else None) if key]
        spec = next((mapping[key] for key in keys if key in mapping), None)
        if spec is None:
            continue
        if spec.title is not None:
            _set_child_text(frame, qn("svg", "title"), spec.title)
        if spec.description is not None:
            _set_child_text(frame, qn("svg", "desc"), spec.description)
        changed += 1
    return changed


def apply_table_headers(tree: etree._ElementTree, mapping: dict[str, int]) -> int:
    """Wrap explicitly selected leading rows as semantic table headers.

    Returns
    -------
    int
        The number of tables whose rows were wrapped.

    Raises
    ------
    ValueError
        A header count is nonpositive or exceeds the direct table rows.

    """
    changed = 0
    for table in select_elements(tree, "//table:table"):
        name = table.get(qn("table", "name"))
        if not name or name not in mapping:
            continue
        count = mapping[name]
        if count < 1:
            msg = f"Header-row count for {name!r} must be >= 1"
            raise ValueError(msg)
        existing = table.find("table:table-header-rows", NS)
        if existing is not None:
            continue
        rows = select_elements(table, "./table:table-row")
        if len(rows) < count:
            msg = f"Table {name!r} has only {len(rows)} direct row(s), not {count}."
            raise ValueError(msg)
        wrapper = etree.Element(qn("table", "table-header-rows"))
        first_index = table.index(rows[0])
        table.insert(first_index, wrapper)
        for row in rows[:count]:
            wrapper.append(row)
        changed += 1
    return changed


def remove_empty_spacer_paragraphs(tree: etree._ElementTree, catalog: StyleCatalog) -> int:
    """Remove empty body spacers while preserving structural and break semantics.

    Returns
    -------
    int
        The number of removed body paragraphs.

    """
    removed = 0
    for p in list(select_elements(tree, "//text:p")):
        if not is_empty_paragraph(p):
            continue
        if select_elements(
            p,
            (
                "ancestor::table:table-cell | ancestor::draw:text-box | "
                "ancestor::office:annotation | ancestor::text:list-item"
            ),
        ):
            continue
        style_name = p.get(qn("text", "style-name"))
        if catalog.has_break_semantics(style_name):
            continue
        parent = p.getparent()
        if parent is None:
            continue
        parent.remove(p)
        removed += 1
    return removed


def _set_child_text(parent: etree._Element, tag: str, text: str) -> None:
    node = parent.find(tag)
    if node is None:
        node = etree.Element(tag)
        # Accessibility title/desc should precede the image/object where possible.
        parent.insert(0, node)
    node.text = text


def _set_version_declarations(
    version_trees: list[etree._ElementTree],
    manifest: etree._ElementTree,
    target_version: str | None,
    changes: list[str],
) -> None:
    if not target_version:
        return
    changed = False
    for tree in version_trees:
        root = tree.getroot()
        if root.get(qn("office", "version")) != target_version:
            root.set(qn("office", "version"), target_version)
            changed = True
    mroot = manifest.getroot()
    if mroot.get(qn("manifest", "version")) != target_version:
        mroot.set(qn("manifest", "version"), target_version)
        changed = True
    root_entries = select_elements(mroot, "./manifest:file-entry[@manifest:full-path='/']")
    if root_entries:
        root_entry = root_entries[0]
        if root_entry.get(qn("manifest", "version")) != target_version:
            root_entry.set(qn("manifest", "version"), target_version)
            changed = True
        if root_entry.get(qn("manifest", "media-type")) != ODT_MIMETYPE:
            root_entry.set(qn("manifest", "media-type"), ODT_MIMETYPE)
            changed = True
    if changed:
        changes.append(f"Set ODF package declarations to version {target_version}.")


def _apply_document_metadata(
    meta: etree._ElementTree,
    styles: etree._ElementTree,
    options: RemediationOptions,
    changes: list[str],
) -> None:
    if options.title is not None and set_metadata_text(
        meta, qn("dc", "title"), options.title.strip()
    ):
        changes.append("Set document title metadata.")

    if options.description is not None and set_metadata_text(
        meta, qn("dc", "description"), options.description.strip()
    ):
        changes.append("Set document description metadata.")

    if options.language is not None:
        language = options.language.strip()
        if set_metadata_text(meta, qn("dc", "language"), language):
            changes.append(f"Set document language metadata to {language}.")
        if set_default_style_language(styles, language):
            changes.append(f"Set default paragraph-style language to {language}.")


def _remove_spacers(
    package: OdtPackage,
    content: etree._ElementTree,
    options: RemediationOptions,
    changes: list[str],
) -> int:
    if not options.remove_empty_spacers:
        return 0
    # Resolve break semantics against the edited content before selecting spacers.
    temp_package = package.clone()
    temp_package.write_xml("content.xml", content)
    count = remove_empty_spacer_paragraphs(content, StyleCatalog(temp_package))
    if count:
        changes.append(f"Removed {count} empty body spacer paragraph(s) without break semantics.")
    return count
