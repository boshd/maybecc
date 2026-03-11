"""Public parser interface for .mcc spec files.

Usage::

    from maybecc.parser import parse

    module = parse(open("example.mcc").read())
    for fn in module.functions:
        print(fn.name, fn.annotations)
"""

from __future__ import annotations

from pathlib import Path

from lark import Lark

from maybecc.parser.ast_nodes import Module
from maybecc.parser.preprocessor import preprocess
from maybecc.parser.transformer import MccTransformer

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"

_parser: Lark | None = None


def _get_parser() -> Lark:
    global _parser
    if _parser is None:
        _parser = Lark(
            _GRAMMAR_PATH.read_text(),
            parser="lalr",
            propagate_positions=True,
        )
    return _parser


def parse(source: str) -> Module:
    """Parse a ``.mcc`` spec string into a typed :class:`Module` AST.

    Raises ``lark.exceptions.UnexpectedInput`` on syntax errors.
    """
    pp = preprocess(source)
    tree = _get_parser().parse(pp.source)
    transformer = MccTransformer(
        bodies=pp.bodies,
        complexities=pp.complexities,
    )
    return transformer.transform(tree)


def parse_file(path: str | Path) -> Module:
    """Parse a ``.mcc`` file from disk."""
    return parse(Path(path).read_text())
