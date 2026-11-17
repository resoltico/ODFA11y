# SPDX-License-Identifier: AGPL-3.0-only
"""Keep XML name ownership central and XPath values separate from expressions."""

import ast

from lxml import etree

from odfa11y.odf import names
from odfa11y.odf.xpath import select_elements
from tests.fixtures.paths import REPOSITORY


def test_clark_names_have_one_owner() -> None:
    violations = []
    for path in (REPOSITORY / "src/odfa11y").rglob("*.py"):
        if path == REPOSITORY / "src/odfa11y/odf/names.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith(("{urn:", "{http:", "{https:"))
            ):
                violations.append(f"{path.relative_to(REPOSITORY)}:{node.lineno}")
    assert not violations, "\n".join(violations)


def test_xpath_values_are_bound_without_changing_the_expression() -> None:
    root = etree.Element(names.OFFICE_STYLES)
    style = etree.SubElement(root, names.STYLE_DEFAULT_STYLE)
    style.set(names.STYLE_FAMILY, "paragraph")
    expression = "./style:default-style[@style:family=$family]"
    assert select_elements(root, expression, family="paragraph") == [style]
    assert select_elements(root, expression, family="paragraph' or '1'='1") == []
