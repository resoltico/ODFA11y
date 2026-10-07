# SPDX-License-Identifier: MPL-2.0
"""Inspect database privacy, declared bindings and descriptions without executing anything."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from odfa11y.odf import PackageStorage, Part, qn, select_elements
from odfa11y.report import Location, rules

from .descriptions import description_attribute, fingerprint, targets

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

CREDENTIALS = re.compile(
    r"(?:password|passwd|pwd|user|username|token|secret)\s*[=:]|://[^/\s]+@", re.IGNORECASE
)
CONFIG = "{urn:oasis:names:tc:opendocument:xmlns:config:1.0}"
AUTHENTICATION_SETTINGS = {
    "password",
    "passwd",
    "pwd",
    "user",
    "username",
    "auth",
    "authorization",
    "authentication",
    "authtoken",
    "authenticationtoken",
    "accesstoken",
    "refreshtoken",
    "bearertoken",
    "token",
    "secret",
    "clientsecret",
    "apikey",
}


def audit_database(document: OdfDocument, report: Report) -> None:
    """Read declarations and package bytes; never open a DB or execute SQL/macros."""
    tree = document.tree(Part.CONTENT)
    databases = select_elements(tree, "//office:body/office:database")
    if len(databases) != 1:
        report.add(rules.BASE001, location=Location("content/database"))
        return
    resources = select_elements(
        databases[0],
        ".//db:connection-resource | .//db:file-based-database | .//db:server-database",
    )
    report.metadata["connection_declarations"] = len(resources)
    if not resources:
        report.add(
            rules.BASE001,
            "Database declares no connection resource.",
            location=Location("content/database"),
        )
    names = (
        tuple(document.storage.member_names())
        if isinstance(document.storage, PackageStorage)
        else ()
    )
    _connections(resources, names, report)
    logins = select_elements(databases[0], ".//db:login")
    if any(node.get(qn("db", "user-name")) for node in logins):
        report.add(rules.BASE003, "Database stores a login identity; its value is not reported.")
    _sensitive_settings(document, report)
    _objects(document, report)
    _executable_content(document, databases[0], report)


def _connections(resources: list[etree._Element], names: tuple[str, ...], report: Report) -> None:
    for resource in resources:
        connection = resource.get(qn("xlink", "href"), "")
        if not connection.startswith("sdbc:embedded:"):
            report.add(rules.BASE002, "Database connection is external; it was not opened.")
        elif not any(name.startswith("database/") and not name.endswith("/") for name in names):
            report.add(rules.BASE001, "Embedded database connection has no embedded storage.")
        if CREDENTIALS.search(connection):
            report.add(
                rules.BASE003,
                "Connection declares credentials; values are not reported.",
            )


def _sensitive_settings(document: OdfDocument, report: Report) -> None:
    for tree in document.distinct_trees(Part.CONTENT, Part.SETTINGS):
        for node in tree.iter():
            if node.tag == qn("db", "data-source-setting"):
                name = node.get(qn("db", "data-source-setting-name"), "")
                kind = node.get(qn("db", "data-source-setting-type"))
                values = node.iter(qn("db", "data-source-setting-value"))
            elif node.tag == CONFIG + "config-item":
                name = node.get(CONFIG + "name", "")
                kind = node.get(CONFIG + "type")
                values = (node,)
            else:
                continue
            identity = "".join(character for character in name.lower() if character.isalnum())
            if (
                kind != "boolean"
                and identity in AUTHENTICATION_SETTINGS
                and any("".join(value.itertext()).strip() for value in values)
            ):
                report.add(
                    rules.BASE003,
                    "Database stores authentication settings; values are not reported.",
                )
                return


def _objects(document: OdfDocument, report: Report) -> None:
    declarations = targets(document)
    for path, matches in declarations.items():
        if len(matches) != 1:
            report.add(
                rules.BASE004, "Database object target is ambiguous.", location=Location(path)
            )
        elif not (matches[0].get(description_attribute(matches[0])) or "").strip():
            report.add(
                rules.BASE004,
                location=Location(path),
                details={"target": path, "fingerprint": fingerprint(matches[0])},
            )


def _executable_content(document: OdfDocument, database: etree._Element, report: Report) -> None:
    queries = select_elements(database, ".//db:query")
    report.metadata["query_declarations"] = len(queries)
    if queries:
        report.add(rules.BASE006, details={"query_count": len(queries)})
    scripts = select_elements(document.tree(Part.CONTENT), "//office:scripts/*")
    names = (
        tuple(document.storage.member_names())
        if isinstance(document.storage, PackageStorage)
        else ()
    )
    if scripts or any(name.startswith(("Basic/", "Scripts/")) for name in names):
        report.add(rules.BASE005)
    components = select_elements(database, ".//db:component")
    if components:
        report.add(
            rules.BASE006,
            "Forms and reports require native review; their payloads remain opaque.",
            details={"component_count": len(components)},
        )
