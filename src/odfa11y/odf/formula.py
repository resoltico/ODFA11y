# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded OpenFormula lexical dependency classification, without evaluation."""

import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from functools import partial
from pathlib import Path
lazy from collections.abc import Callable

lazy from lxml import etree

from odfa11y.odf import names as xml_names

OPENFORMULA = "urn:oasis:names:tc:opendocument:xmlns:of:1.2"
MAX_CHARACTERS = 32768
MAX_TOKENS = 4096
MAX_DEPTH = 64
TABLE = tomllib.loads((Path(__file__).parent / "formula_data/functions.toml").read_text())
FUNCTIONS = frozenset(TABLE["functions"])
CELL_QUERIES = frozenset(TABLE["cell_queries"])
INFO_QUERIES = frozenset(TABLE["info_queries"])
TOKEN = re.compile(
    r'\s*(?:"(?:[^"\x00]|"")*"|\[(?:[^\]\x00]|\]\])*\]|'
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|"
    r"#[A-Za-z0-9/?!]+|[A-Za-z_][A-Za-z0-9_.]*|<=|>=|<>|[()+*/^&=<>%;|~!+-])"
)
SHEET = r"\$?(?:[^\]\. #$']+|'(?:[^']|'')*')?"
CELL = r"\$?[A-Za-z]+\$?[1-9][0-9]*"
COLUMN = r"\$?[A-Za-z]+"
ROW = r"\$?[1-9][0-9]*"
REFERENCE = re.compile(
    rf"(?:{SHEET}\.{CELL}(?::{SHEET}\.{CELL})?|"
    rf"{SHEET}\.{COLUMN}:{SHEET}\.{COLUMN}|{SHEET}\.{ROW}:{SHEET}\.{ROW})"
)


@dataclass(frozen=True)
class FormulaAnalysis:
    """Only dependency counts; formula literals never enter diagnostics."""

    loading: int = 0
    identity: int = 0
    incomplete: int = 0

    def __add__(self, other: FormulaAnalysis) -> FormulaAnalysis:
        """Combine independently classified declarations.

        Returns
        -------
        FormulaAnalysis
            The summed counts.

        """
        return FormulaAnalysis(
            self.loading + other.loading,
            self.identity + other.identity,
            self.incomplete + other.incomplete,
        )


class UnestablishedFormulaError(ValueError):
    """The bounded supported syntax cannot classify this expression."""


def classify_formula(
    expression: str, namespaces: dict[str | None, str], resolve: Callable[[str], FormulaAnalysis]
) -> FormulaAnalysis:
    """Classify one original declaration with its original namespace bindings.

    Returns
    -------
    FormulaAnalysis
        Loading, captured-identity and incomplete classification counts.

    """
    if len(expression) > MAX_CHARACTERS:
        return FormulaAnalysis(incomplete=1)
    expression = expression.strip()
    prefix = re.match(r"^([A-Za-z_][A-Za-z0-9_.-]*):", expression)
    if prefix:
        if namespaces.get(prefix[1]) != OPENFORMULA:
            return FormulaAnalysis(incomplete=1)
        expression = expression[prefix.end() :]
    expression = expression.removeprefix("=")
    try:
        parser = FormulaParser(expression, resolve)
        parser.expression(0)
        if parser.index != len(parser.lexemes):
            return FormulaAnalysis(incomplete=1)
    except UnestablishedFormulaError, RecursionError:
        return FormulaAnalysis(incomplete=1)
    return parser.facts


class FormulaParser:
    """Validate lexical structure and inspect calls/references, never cached values."""

    def __init__(self, expression: str, resolve: Callable[[str], FormulaAnalysis]) -> None:
        """Tokenize with a fixed work budget and reject every unmatched character.

        Raises
        ------
        UnestablishedFormulaError
            Syntax or work budget is unestablished.

        """
        self.lexemes: list[str] = []
        cursor = 0
        while cursor < len(expression.rstrip()):
            match = TOKEN.match(expression, cursor)
            if match is None or len(self.lexemes) >= MAX_TOKENS:
                raise UnestablishedFormulaError
            self.lexemes.append(match[0].strip())
            cursor = match.end()
        self.index = 0
        self.facts = FormulaAnalysis()
        self.resolve = resolve

    def peek(self) -> str:
        """Return the next lexeme without consuming it.

        Returns
        -------
        str
            Token, or the empty sentinel at end.

        """
        return self.lexemes[self.index] if self.index < len(self.lexemes) else ""

    def take(self) -> str:
        """Consume one required lexeme.

        Returns
        -------
        str
            The next lexeme.

        Raises
        ------
        UnestablishedFormulaError
            The input ended unexpectedly.

        """
        value = self.peek()
        if not value:
            raise UnestablishedFormulaError
        self.index += 1
        return value

    def expression(self, depth: int) -> str | None:
        """Inspect an expression; retain only a sole string literal for query calls.

        Returns
        -------
        str | None
            A literal query, or None for a dynamic/composed argument.

        Raises
        ------
        UnestablishedFormulaError
            Syntax or work budget is unestablished.

        """
        if depth >= MAX_DEPTH:
            raise UnestablishedFormulaError
        value = self.primary(depth + 1)
        while self.peek() in {
            "+",
            "-",
            "*",
            "/",
            "^",
            "&",
            "=",
            "<",
            ">",
            "<=",
            ">=",
            "<>",
            "~",
            "!",
        }:
            self.take()
            self.primary(depth + 1)
            value = None
        return value

    def primary(self, depth: int) -> str | None:
        """Inspect one scalar, reference, grouped expression or function call.

        Returns
        -------
        str | None
            A sole string literal, when present.

        Raises
        ------
        UnestablishedFormulaError
            Syntax or work budget is unestablished.

        """
        if depth >= MAX_DEPTH:
            raise UnestablishedFormulaError
        lexeme = self.take()
        value = None
        if lexeme in {"+", "-"}:
            self.primary(depth + 1)
        elif lexeme == "(":
            self.expression(depth + 1)
            if self.take() != ")":
                raise UnestablishedFormulaError
        elif lexeme.startswith('"'):
            value = lexeme[1:-1].replace('""', '"')
        elif lexeme.startswith("["):
            self.reference(lexeme[1:-1])
        elif (
            lexeme[0].isdigit()
            or lexeme.startswith(".")
            or lexeme in {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}
        ):
            pass
        else:
            self.identifier(lexeme, depth)
        if self.peek() == "%":
            self.take()
            value = None
        return value

    def identifier(self, lexeme: str, depth: int) -> None:
        """Classify a standard function or scoped declaration name.

        Raises
        ------
        UnestablishedFormulaError
            The identifier is malformed.

        """
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", lexeme):
            raise UnestablishedFormulaError
        if self.peek() == "(":
            self.call(lexeme.upper(), depth + 1)
        elif lexeme.upper() not in {"TRUE", "FALSE"}:
            self.facts += self.resolve(lexeme)

    def reference(self, lexeme: str) -> None:
        """Distinguish explicit external sources from supported local cell/ranges.

        Raises
        ------
        UnestablishedFormulaError
            Syntax or work budget is unestablished.

        """
        if lexeme == "#REF!":
            return
        if "#" in lexeme:
            self.facts += FormulaAnalysis(loading=1)
        elif not REFERENCE.fullmatch(lexeme):
            raise UnestablishedFormulaError

    def call(self, name: str, depth: int) -> None:
        """Inspect all branches/arguments and apply the normative sensitive-call policy.

        Raises
        ------
        UnestablishedFormulaError
            Syntax or work budget is unestablished.

        """
        if name not in FUNCTIONS or depth >= MAX_DEPTH:
            raise UnestablishedFormulaError
        self.take()  # Opening parenthesis.
        arguments: list[str | None] = []
        if self.peek() != ")":
            arguments.append(self.expression(depth + 1))
            while self.peek() == ";":
                self.take()
                arguments.append(None if self.peek() in {";", ")"} else self.expression(depth + 1))
        if self.take() != ")":
            raise UnestablishedFormulaError
        self.facts += _call_facts(name, arguments)


def _call_facts(name: str, arguments: list[str | None]) -> FormulaAnalysis:
    if name in TABLE["loading_functions"]:
        return FormulaAnalysis(loading=1)
    if name in TABLE["dynamic_functions"]:
        return FormulaAnalysis(incomplete=1)
    if name not in {"CELL", "INFO"}:
        return FormulaAnalysis()
    query = arguments[0].upper() if arguments and arguments[0] is not None else None
    supported = CELL_QUERIES if name == "CELL" else INFO_QUERIES
    if query not in supported:
        return FormulaAnalysis(incomplete=1)
    if query in TABLE["identity_queries"][name]:
        return FormulaAnalysis(identity=1)
    return FormulaAnalysis()


FORMULA_ATTRIBUTES = frozenset({
    xml_names.STYLE_CONDITION,
    xml_names.TABLE_CONDITION,
    xml_names.TABLE_EXPRESSION,
    xml_names.TABLE_FORMULA,
    xml_names.TEXT_FORMULA,
})


REFERENCE_ATTRIBUTES = frozenset({
    xml_names.STYLE_BASE_CELL_ADDRESS,
    xml_names.TABLE_BASE_CELL_ADDRESS,
    xml_names.TABLE_CELL_RANGE_ADDRESS,
})


NAMED_TAGS = frozenset({xml_names.TABLE_NAMED_EXPRESSION, xml_names.TABLE_NAMED_RANGE})


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
                self.names[self.scope(node), node.get(xml_names.TABLE_NAME, "").casefold()].append(
                    node
                )

    def scope(self, node: etree._Element) -> etree._Element:
        """Find the enclosing worksheet, otherwise document global scope.

        Returns
        -------
        etree._Element
            The scope owner.

        """
        return next((p for p in node.iterancestors(xml_names.TABLE_TABLE)), self.root)

    def inspect(self) -> FormulaAnalysis:
        """Classify all five attribute contexts and named ranges independently.

        Returns
        -------
        FormulaAnalysis
            Counts with bounded named-expression dependency traversal.

        """
        facts = FormulaAnalysis()
        for node in self.root.iter():
            declarations = [node.attrib[a] for a in FORMULA_ATTRIBUTES if a in node.attrib]
            declarations.extend(
                "[" + node.attrib[a] + "]" for a in REFERENCE_ATTRIBUTES if a in node.attrib
            )
            if (
                node.tag == xml_names.TABLE_SOURCE_CELL_RANGE
                and xml_names.TABLE_CELL_RANGE_ADDRESS not in node.attrib
            ):
                declarations.append(node.get(xml_names.TABLE_NAME, ""))
            if node.tag == xml_names.TABLE_CELL_RANGE_SOURCE:
                facts += FormulaAnalysis(incomplete=1)
                self.inspected += 1
            for expression in declarations:
                if self.inspected >= MAX_DECLARATIONS:
                    return facts + FormulaAnalysis(incomplete=1)
                self.inspected += 1
                facts += self.classify(node, expression, frozenset())
        return facts

    def classify(
        self, node: etree._Element, expression: str, active: frozenset[etree._Element]
    ) -> FormulaAnalysis:
        """Follow referenced names using original declaration namespace bindings.

        Returns
        -------
        FormulaAnalysis
            Declaration dependency counts.

        """
        pending = [(node, expression, active)]
        facts = FormulaAnalysis()
        while pending:
            origin, declaration, ancestors = pending.pop()
            facts += classify_formula(
                declaration,
                origin.nsmap,
                partial(self.resolve, origin, active=ancestors, pending=pending),
            )
        return facts

    def resolve(
        self,
        origin: etree._Element,
        name: str,
        active: frozenset[etree._Element],
        pending: list[tuple[etree._Element, str, frozenset[etree._Element]]],
    ) -> FormulaAnalysis:
        """Resolve one name, refusing missing, ambiguous, cyclic or oversized work.

        Returns
        -------
        FormulaAnalysis
            The declaration's classification or an explicit incomplete result.

        """
        self.work += 1
        name = name.casefold()
        nodes = self.names.get((self.scope(origin), name), self.names.get((self.root, name), []))
        if len(nodes) != 1 or self.work > MAX_NAME_WORK or len(active) >= MAX_NAME_DEPTH:
            return FormulaAnalysis(incomplete=1)
        node = nodes[0]
        if node in active:
            return FormulaAnalysis(incomplete=1)
        expression = node.get(xml_names.TABLE_EXPRESSION)
        if expression is None:
            expression = "[" + node.get(xml_names.TABLE_CELL_RANGE_ADDRESS, "") + "]"
        pending.append((node, expression, active | {node}))
        return FormulaAnalysis()
