from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List

from app.keywords import normalize_keyword


@dataclass(frozen=True)
class Term:
    value: str
    is_prefix: bool = False


@dataclass(frozen=True)
class Not:
    node: "Node"


@dataclass(frozen=True)
class And:
    nodes: List["Node"]


@dataclass(frozen=True)
class Or:
    nodes: List["Node"]


Node = Term | Not | And | Or


@dataclass(frozen=True)
class Token:
    kind: str
    value: str = ""


def _tokenize(text: str) -> Iterator[Token]:
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            i += 1
            start = i
            while i < length and text[i] != '"':
                i += 1
            value = text[start:i]
            i += 1
            if value:
                yield Token("TERM", value)
            continue
        if ch == '(':
            i += 1
            yield Token("LPAREN")
            continue
        if ch == ')':
            i += 1
            yield Token("RPAREN")
            continue
        if ch == '-' and i + 1 < length and not text[i + 1].isspace():
            i += 1
            yield Token("NOT")
            continue
        start = i
        while i < length and not text[i].isspace() and text[i] not in '()':
            i += 1
        value = text[start:i]
        if value:
            upper = value.upper()
            if upper == "OR":
                yield Token("OR")
            elif upper == "AND":
                yield Token("AND")
            else:
                yield Token("TERM", value)
    yield Token("EOF")


class Parser:
    def __init__(self, tokens: Iterable[Token]):
        self.tokens = list(tokens)
        self.pos = 0

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _consume(self, kind: str) -> Token:
        token = self._current()
        if token.kind != kind:
            raise ValueError(f"Expected {kind}, got {token.kind}")
        self.pos += 1
        return token

    def parse(self) -> Node | None:
        if self._current().kind == "EOF":
            return None
        node = self._parse_or()
        return node

    def _parse_or(self) -> Node:
        nodes = [self._parse_and()]
        while self._current().kind == "OR":
            self._consume("OR")
            nodes.append(self._parse_and())
        if len(nodes) == 1:
            return nodes[0]
        return Or(nodes)

    def _parse_and(self) -> Node:
        nodes = []
        while self._current().kind in {"TERM", "NOT", "LPAREN"}:
            nodes.append(self._parse_factor())
            if self._current().kind == "AND":
                self._consume("AND")
        if not nodes:
            return Term("")
        if len(nodes) == 1:
            return nodes[0]
        return And(nodes)

    def _parse_factor(self) -> Node:
        if self._current().kind == "NOT":
            self._consume("NOT")
            return Not(self._parse_factor())
        if self._current().kind == "LPAREN":
            self._consume("LPAREN")
            node = self._parse_or()
            self._consume("RPAREN")
            return node
        token = self._consume("TERM")
        value = token.value
        is_prefix = value.endswith("*") and len(value) > 1
        if is_prefix:
            value = value[:-1]
        return Term(value=value, is_prefix=is_prefix)


def parse_query(text: str) -> Node | None:
    parser = Parser(_tokenize(text))
    try:
        return parser.parse()
    except ValueError:
        return None


def extract_positive_terms(node: Node | None) -> list[str]:
    terms: list[str] = []
    if node is None:
        return terms

    def _walk(n: Node) -> None:
        if isinstance(n, Term):
            if n.value:
                terms.append(n.value)
        elif isinstance(n, Not):
            return
        elif isinstance(n, And) or isinstance(n, Or):
            for child in n.nodes:
                _walk(child)

    _walk(node)
    return terms


def compile_filter(node: Node | None) -> str | None:
    if node is None:
        return None

    def _term_filter(term: Term) -> str | None:
        norm = normalize_keyword(term.value)
        if not norm:
            return None
        if term.is_prefix:
            return None
        return f'keywords_norm = "{norm}"'

    def _walk(n: Node) -> str | None:
        if isinstance(n, Term):
            return _term_filter(n)
        if isinstance(n, Not):
            inner = _walk(n.node)
            if inner:
                return f"NOT ({inner})"
            return None
        if isinstance(n, And):
            parts = [part for child in n.nodes if (part := _walk(child))]
            if not parts:
                return None
            return " AND ".join(f"({p})" for p in parts)
        if isinstance(n, Or):
            parts = [part for child in n.nodes if (part := _walk(child))]
            if not parts:
                return None
            return " OR ".join(f"({p})" for p in parts)
        return None

    return _walk(node)


def evaluate(node: Node | None, keywords_norm: set[str]) -> bool:
    if node is None:
        return True

    def _matches_term(term: Term) -> bool:
        norm = normalize_keyword(term.value)
        if not norm:
            return True
        if term.is_prefix:
            return any(k.startswith(norm) for k in keywords_norm)
        return norm in keywords_norm

    def _walk(n: Node) -> bool:
        if isinstance(n, Term):
            return _matches_term(n)
        if isinstance(n, Not):
            return not _walk(n.node)
        if isinstance(n, And):
            return all(_walk(child) for child in n.nodes)
        if isinstance(n, Or):
            return any(_walk(child) for child in n.nodes)
        return True

    return _walk(node)
