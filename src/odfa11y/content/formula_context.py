# SPDX-License-Identifier: MPL-2.0
"""Inspect every formula declaration and scoped name in each reachable ODF tree."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from odfa11y.odf import qn

from .formula_syntax import FormulaFacts, classify_formula

if TYPE_CHECKING:
    from lxml import etree

FORMULA_ATTRIBUTES = frozenset({
    qn("style", "condition"),
    qn("table", "condition"),
    qn("table", "expression"),
    qn("table", "formula"),
    qn("text", "formula"),
})
REFERENCE_ATTRIBUTES = frozenset({
    qn("style", "base-cell-address"),
    qn("table", "base-cell-address"),
    qn("table", "cell-range-address"),
})
NAMED_TAGS = frozenset({qn("table", "named-expression"), qn("table", "named-range")})
MAX_DECLARATIONS = 100000
MAX_NAME_WORK = 4096
MAX_NAME_DEPTH = 64


class FormulaContext:
    """Classify declarations with worksheet/global scope and namespace identity."""

    def __init__(self, root: etree._Element) -> None:
        """Index declarations without caching authored expression results."""
        self.root = root
        self.names: dict[tuple[etree._Element, str], list[etree._Element]] = defaultdict(list)
        self.work = 0
        self.inspected = 0
        for node in root.iter():
            if node.tag in NAMED_TAGS:
                self.names[self.scope(node), node.get(qn("table", "name"), "").casefold()].append(
                    node
                )

    def scope(self, node: etree._Element) -> etree._Element:
        """Find the enclosing worksheet, otherwise document global scope.

        Returns
        -------
        etree._Element
            The scope owner.

        """
        return next((p for p in node.iterancestors(qn("table", "table"))), self.root)

    def inspect(self) -> FormulaFacts:
        """Classify all five attribute contexts and named ranges independently.

        Returns
        -------
        FormulaFacts
            Counts with bounded named-expression dependency traversal.

        """
        facts = FormulaFacts()
        for node in self.root.iter():
            declarations = [node.attrib[a] for a in FORMULA_ATTRIBUTES if a in node.attrib]
            declarations.extend(
                "[" + node.attrib[a] + "]" for a in REFERENCE_ATTRIBUTES if a in node.attrib
            )
            if (
                node.tag == qn("table", "source-cell-range")
                and qn("table", "cell-range-address") not in node.attrib
            ):
                declarations.append(node.get(qn("table", "name"), ""))
            if node.tag == qn("table", "cell-range-source"):
                facts += FormulaFacts(incomplete=1)
                self.inspected += 1
            for expression in declarations:
                if self.inspected >= MAX_DECLARATIONS:
                    return facts + FormulaFacts(incomplete=1)
                self.inspected += 1
                facts += self.classify(node, expression, frozenset())
        return facts

    def classify(
        self, node: etree._Element, expression: str, active: frozenset[etree._Element]
    ) -> FormulaFacts:
        """Follow referenced names using original declaration namespace bindings.

        Returns
        -------
        FormulaFacts
            Declaration dependency counts.

        """
        return classify_formula(
            expression, node.nsmap, lambda name: self.resolve(node, name, active)
        )

    def resolve(
        self, origin: etree._Element, name: str, active: frozenset[etree._Element]
    ) -> FormulaFacts:
        """Resolve one name, refusing missing, ambiguous, cyclic or oversized work.

        Returns
        -------
        FormulaFacts
            The declaration's classification or an explicit incomplete result.

        """
        self.work += 1
        name = name.casefold()
        nodes = self.names.get((self.scope(origin), name), self.names.get((self.root, name), []))
        if len(nodes) != 1 or self.work > MAX_NAME_WORK or len(active) >= MAX_NAME_DEPTH:
            return FormulaFacts(incomplete=1)
        node = nodes[0]
        if node in active:
            return FormulaFacts(incomplete=1)
        expression = node.get(qn("table", "expression"))
        if expression is None:
            expression = "[" + node.get(qn("table", "cell-range-address"), "") + "]"
        return self.classify(node, expression, active | {node})
