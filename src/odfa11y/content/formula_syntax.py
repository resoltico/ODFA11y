# SPDX-License-Identifier: MPL-2.0
"""Bounded OpenFormula lexical dependency classification, without evaluation."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

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
class FormulaFacts:
    """Only dependency counts; formula literals never enter diagnostics."""

    loading: int = 0
    identity: int = 0
    incomplete: int = 0

    def __add__(self, other: FormulaFacts) -> FormulaFacts:
        """Combine independently classified declarations.

        Returns
        -------
        FormulaFacts
            The summed counts.

        """
        return FormulaFacts(
            self.loading + other.loading,
            self.identity + other.identity,
            self.incomplete + other.incomplete,
        )


class UnestablishedFormulaError(ValueError):
    """The bounded supported syntax cannot classify this expression."""


def classify_formula(
    expression: str, namespaces: dict[str | None, str], resolve: Callable[[str], FormulaFacts]
) -> FormulaFacts:
    """Classify one original declaration with its original namespace bindings.

    Returns
    -------
    FormulaFacts
        Loading, captured-identity and incomplete classification counts.

    """
    if len(expression) > MAX_CHARACTERS:
        return FormulaFacts(incomplete=1)
    expression = expression.strip()
    prefix = re.match(r"^([A-Za-z_][A-Za-z0-9_.-]*):", expression)
    if prefix:
        if namespaces.get(prefix[1]) != OPENFORMULA:
            return FormulaFacts(incomplete=1)
        expression = expression[prefix.end() :]
    expression = expression.removeprefix("=")
    try:
        parser = FormulaParser(expression, resolve)
        parser.expression(0)
        if parser.index != len(parser.lexemes):
            return FormulaFacts(incomplete=1)
    except UnestablishedFormulaError:
        return FormulaFacts(incomplete=1)
    return parser.facts


class FormulaParser:
    """Validate lexical structure and inspect calls/references, never cached values."""

    def __init__(self, expression: str, resolve: Callable[[str], FormulaFacts]) -> None:
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
        self.facts = FormulaFacts()
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
            self.facts += FormulaFacts(loading=1)
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


def _call_facts(name: str, arguments: list[str | None]) -> FormulaFacts:
    if name in TABLE["loading_functions"]:
        return FormulaFacts(loading=1)
    if name in TABLE["dynamic_functions"]:
        return FormulaFacts(incomplete=1)
    if name not in {"CELL", "INFO"}:
        return FormulaFacts()
    query = arguments[0].upper() if arguments and arguments[0] is not None else None
    supported = CELL_QUERIES if name == "CELL" else INFO_QUERIES
    if query not in supported:
        return FormulaFacts(incomplete=1)
    if query in TABLE["identity_queries"][name]:
        return FormulaFacts(identity=1)
    return FormulaFacts()
