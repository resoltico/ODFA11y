# SPDX-License-Identifier: MPL-2.0
"""Inspect database privacy, declared bindings and descriptions without executing anything."""

import re
from typing import Annotated, Literal
lazy from dataclasses import dataclass, field

from lxml import etree

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.contracts import Description
from odfa11y.decisions import OpenDecision
from odfa11y.families.database.descriptions import description_attribute, fingerprint
from odfa11y.families.database.domain import OBJECTS
from odfa11y.families.database.kinds import DATABASE_DESCRIPTION
from odfa11y.odf import PackageStorage, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

CREDENTIALS = re.compile(
    r"(?:password|passwd|pwd|user|username|token|secret)\s*[=:]|://[^/\s]+@", re.IGNORECASE
)
CONFIG = xml_names.CONFIG_NAMESPACE
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


@dataclass(frozen=True, slots=True)
class DatabaseMeasurements:
    """Measurements produced by database analysis; None denotes unmeasured data."""

    producer: Literal["database"] = field(default="database", init=False)
    connection_declaration_count: Annotated[
        int | None, Description("Database connection declarations.")
    ] = None
    query_declaration_count: Annotated[int | None, Description("Declared database queries.")] = None


def audit_database(document: OdfDocument, report: Report, metadata: DocumentMetadata) -> None:
    """Read declarations and package bytes; never open a DB or execute SQL/macros."""
    tree = document.tree(Part.CONTENT)
    databases = select_elements(tree, "//office:body/office:database")
    if len(databases) != 1:
        report.raise_(rules.DATABASE001, location=Location("content/database"))
        return
    report.observe_review(Topic.SOURCE_BOUNDARY)
    resources = select_elements(
        databases[0],
        ".//db:connection-resource | .//db:file-based-database | .//db:server-database",
    )
    report.measure(DatabaseMeasurements(connection_declaration_count=len(resources)))
    if not resources:
        report.raise_(
            rules.DATABASE002,
            "Database declares no connection resource.",
            location=Location("content/database"),
        )
    names = (
        tuple(document.storage.member_names())
        if isinstance(document.storage, PackageStorage)
        else ()
    )
    if resources or any(name.startswith("database/") for name in names):
        report.observe_review(Topic.PRIVACY_AND_EXECUTION)
    _connections(resources, names, report)
    logins = select_elements(databases[0], ".//db:login")
    if logins:
        report.observe_review(Topic.PRIVACY_AND_EXECUTION)
    if any(node.get(xml_names.DB_USER_NAME) for node in logins):
        report.raise_(
            rules.DATABASE005, "Database stores a login identity; its value is not reported."
        )
    _sensitive_settings(document, report)
    _objects(document, report)
    _executable_content(document, databases[0], report)


def _connections(resources: list[etree._Element], names: tuple[str, ...], report: Report) -> None:
    for resource in resources:
        connection = resource.get(xml_names.XLINK_HREF, "")
        if not connection.startswith("sdbc:embedded:"):
            report.raise_(rules.DATABASE004, "Database connection is external; it was not opened.")
        elif not any(name.startswith("database/") and not name.endswith("/") for name in names):
            report.raise_(
                rules.DATABASE003, "Embedded database connection has no embedded storage."
            )
        if CREDENTIALS.search(connection):
            report.raise_(
                rules.DATABASE006,
                "Connection declares credentials; values are not reported.",
            )


def _sensitive_settings(document: OdfDocument, report: Report) -> None:
    for tree in document.distinct_trees(Part.CONTENT, Part.SETTINGS):
        for node in tree.iter():
            if node.tag == xml_names.DB_DATA_SOURCE_SETTING:
                name = node.get(xml_names.DB_DATA_SOURCE_SETTING_NAME, "")
                kind = node.get(xml_names.DB_DATA_SOURCE_SETTING_TYPE)
                values = node.iter(xml_names.DB_DATA_SOURCE_SETTING_VALUE)
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
                report.observe_review(Topic.PRIVACY_AND_EXECUTION)
                report.raise_(
                    rules.DATABASE007,
                    "Database stores authentication settings; values are not reported.",
                )
                return


def _objects(document: OdfDocument, report: Report) -> None:
    declarations = OBJECTS.inspect(document).nodes
    if declarations:
        report.observe_review(Topic.DATABASE_MEANING)
    for path, matches in declarations.items():
        if len(matches) != 1:
            report.raise_(
                rules.DATABASE008, "Database object target is ambiguous.", location=Location(path)
            )
        elif not (matches[0].get(description_attribute(matches[0])) or "").strip():
            report.raise_(
                rules.DATABASE009,
                location=Location(path),
                decision=OpenDecision(
                    DATABASE_DESCRIPTION,
                    Target((Location(path)).path, Fingerprint(fingerprint(matches[0]))),
                    {"text": matches[0].get(description_attribute(matches[0]))},
                ),
            )


def _executable_content(document: OdfDocument, database: etree._Element, report: Report) -> None:
    queries = select_elements(database, ".//db:query")
    report.measure(DatabaseMeasurements(query_declaration_count=len(queries)))
    if queries:
        report.observe_review(Topic.PRIVACY_AND_EXECUTION)
        report.raise_(rules.DATABASE011, details={"query_count": len(queries)})
    scripts = select_elements(document.tree(Part.CONTENT), "//office:scripts/*")
    names = (
        tuple(document.storage.member_names())
        if isinstance(document.storage, PackageStorage)
        else ()
    )
    if scripts or any(name.startswith(("Basic/", "Scripts/")) for name in names):
        report.observe_review(Topic.PRIVACY_AND_EXECUTION)
        report.raise_(rules.DATABASE010)
    components = select_elements(database, ".//db:component")
    if components:
        report.observe_review(Topic.PRIVACY_AND_EXECUTION)
        report.raise_(
            rules.DATABASE012,
            "Forms and reports require native review; their payloads remain opaque.",
            details={"component_count": len(components)},
        )
