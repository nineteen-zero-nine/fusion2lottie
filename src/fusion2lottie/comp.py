"""Reading Fusion compositions: the Lua-like tables Fusion and DaVinci Resolve save (.comp, .setting)."""
from __future__ import annotations

import json
import re

_TOKEN = re.compile(r'\s+|--[^\n]*|(?P<str>"(?:[^"\\]|\\.)*")|(?P<num>-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'
                    r'|(?P<name>[A-Za-z_][\w.]*)|(?P<sym>[{}\[\]=,;])')


class Table(dict):
    """A Fusion table: named fields as dict items, positional values in `.items_`, and the type name of a typed
    table such as `Input { ... }` in `.kind` (None for a plain `{ ... }`).

    A table of positional values only, like a keyframe handle `{ 32, 25.3 }`, is an empty dict: test for None,
    not for truth.
    """

    def __init__(self, kind: str | None = None):
        super().__init__()
        self.kind = kind
        self.items_: list = []


class CompSyntaxError(ValueError):
    pass


def parse(text: str):
    """Parse the text of a .comp or .setting file into Tables, numbers (floats), strings and booleans."""
    toks = [(m.lastgroup, m.group(m.lastgroup)) for m in _TOKEN.finditer(text) if m.lastgroup]
    pos = 0

    def peek(k=0):
        return toks[pos + k] if pos + k < len(toks) else (None, None)

    def take(expect=None):
        nonlocal pos
        if pos >= len(toks):
            raise CompSyntaxError("unexpected end of file")
        tok = toks[pos]
        if expect and tok[1] != expect:
            raise CompSyntaxError(f"expected {expect!r}, found {tok[1]!r} (token {pos})")
        pos += 1
        return tok

    def value():
        kind, tok = peek()
        if tok == "{":
            return table(None)
        take()
        if kind == "str":
            return json.loads(tok)
        if kind == "num":
            return float(tok)
        if tok in ("true", "false"):
            return tok == "true"
        if tok == "nil":
            return None
        if kind == "name" and peek()[1] == "{":
            return table(tok)
        if kind == "name":
            return tok
        raise CompSyntaxError(f"unexpected {tok!r} (token {pos - 1})")

    def table(kind):
        t = Table(kind)
        take("{")
        while peek()[1] != "}":
            if peek()[1] == "[":
                take("[")
                key = value()
                take("]")
                take("=")
                t[key] = value()
            elif peek()[0] == "name" and peek(1)[1] == "=":
                key = take()[1]
                take("=")
                t[key] = value()
            else:
                t.items_.append(value())
            if peek()[1] in (",", ";"):
                take()
        take("}")
        return t

    result = value()
    if pos != len(toks):
        raise CompSyntaxError(f"unexpected {peek()[1]!r} after the composition (token {pos})")
    return result
