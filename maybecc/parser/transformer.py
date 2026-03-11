"""Lark Tree -> typed AST transformer.

Converts the raw Lark parse tree into the typed dataclass AST defined in
``ast_nodes``.  Requires the extracted body and complexity strings from the
preprocessor to reattach to the appropriate AST nodes.
"""

from __future__ import annotations

import re
from typing import Any

from lark import Token, Transformer, Tree

from maybecc.parser.ast_nodes import (
    ArrayType,
    BinaryOp,
    BoolLit,
    CallExpr,
    NullLit,
    Complexity,
    Directive,
    EnumDef,
    Field,
    FieldAccess,
    FlagAnnotation,
    FuncDef,
    Ident,
    IndexExpr,
    KeyedArg,
    Module,
    NumberLit,
    OptionType,
    Param,
    ParamAnnotation,
    PositionalArg,
    Postcondition,
    Precondition,
    PtrType,
    ResultType,
    SimpleType,
    SliceType,
    StructDef,
    UnaryOp,
)

_BODY_RE = re.compile(r"__BODY_(\d+)__")
_CMPLX_RE = re.compile(r"__CMPLX_(\d+)__")


class MccTransformer(Transformer):
    """Bottom-up transformer from Lark parse tree to typed AST."""

    def __init__(
        self,
        bodies: list[str] | None = None,
        complexities: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._bodies = bodies or []
        self._complexities = complexities or []

    # ------------------------------------------------------------------
    # Top level
    # ------------------------------------------------------------------

    def start(self, items: list[Any]) -> Module:
        directives = tuple(i for i in items if isinstance(i, Directive))
        structs = tuple(i for i in items if isinstance(i, StructDef))
        enums = tuple(i for i in items if isinstance(i, EnumDef))
        functions = tuple(i for i in items if isinstance(i, FuncDef))
        return Module(
            directives=directives,
            structs=structs,
            enums=enums,
            functions=functions,
        )

    # ------------------------------------------------------------------
    # Directives
    # ------------------------------------------------------------------

    def top_directive(self, children: list[Any]) -> Directive:
        name = str(children[0])
        args = children[1]
        return Directive(name=name, args=args)

    def directive_args(self, children: list[Any]) -> tuple:
        return tuple(children)

    def keyed_arg(self, children: list[Any]) -> KeyedArg:
        return KeyedArg(key=str(children[0]), value=children[1])

    def positional_arg(self, children: list[Any]) -> PositionalArg:
        return PositionalArg(value=children[0])

    def atom_number(self, children: list[Any]) -> int:
        return int(children[0])

    def atom_name(self, children: list[Any]) -> str:
        return str(children[0])

    # ------------------------------------------------------------------
    # Struct
    # ------------------------------------------------------------------

    def struct_def(self, children: list[Any]) -> StructDef:
        name = str(children[0])
        fields = tuple(children[1:])
        return StructDef(name=name, fields=fields)

    def field(self, children: list[Any]) -> Field:
        return Field(name=str(children[0]), type=children[1])

    # ------------------------------------------------------------------
    # Enum
    # ------------------------------------------------------------------

    def enum_def(self, children: list[Any]) -> EnumDef:
        name = str(children[0])
        variants = children[1]
        return EnumDef(name=name, variants=variants)

    def enum_body(self, children: list[Any]) -> tuple[str, ...]:
        return tuple(str(c) for c in children)

    # ------------------------------------------------------------------
    # Function
    # ------------------------------------------------------------------

    def func_def(self, children: list[Any]) -> FuncDef:
        name = str(children[0])
        sentinel = str(children[-1])  # BODY_SENTINEL is always last

        params: tuple = ()
        return_type = None
        annotations: list = []

        for child in children[1:-1]:
            if isinstance(child, tuple) and child and isinstance(child[0], Param):
                params = child
            elif isinstance(child, Tree) and child.data == "return_type":
                return_type = child.children[0]
            elif isinstance(
                child,
                (Precondition, Postcondition, Complexity, FlagAnnotation, ParamAnnotation),
            ):
                annotations.append(child)

        body_match = _BODY_RE.match(sentinel)
        body_lines: tuple[str, ...] = ()
        if body_match:
            idx = int(body_match.group(1))
            raw = self._bodies[idx]
            body_lines = _parse_body(raw)

        return FuncDef(
            name=name,
            params=params,
            return_type=return_type,
            annotations=tuple(annotations),
            body=body_lines,
        )

    def return_type(self, children: list[Any]) -> Tree:
        # children: [Token(ARROW, '->'), type_expr] — keep only the type
        return Tree("return_type", [children[-1]])

    def param_list(self, children: list[Any]) -> tuple[Param, ...]:
        return tuple(children)

    def param(self, children: list[Any]) -> Param:
        return Param(name=str(children[0]), type=children[1])

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    def precondition(self, children: list[Any]) -> Precondition:
        return Precondition(expr=children[0])

    def postcondition(self, children: list[Any]) -> Postcondition:
        return Postcondition(expr=children[0])

    def complexity(self, children: list[Any]) -> Complexity:
        sentinel = str(children[0])
        cmplx_match = _CMPLX_RE.match(sentinel)
        if cmplx_match:
            idx = int(cmplx_match.group(1))
            return Complexity(text=self._complexities[idx])
        return Complexity(text=sentinel)

    def flag_annotation(self, children: list[Any]) -> FlagAnnotation:
        return FlagAnnotation(name=str(children[0]))

    def param_annotation(self, children: list[Any]) -> ParamAnnotation:
        return ParamAnnotation(name=str(children[0]), args=children[1])

    # ------------------------------------------------------------------
    # Type expressions
    # ------------------------------------------------------------------

    def simple_type(self, children: list[Any]) -> SimpleType:
        return SimpleType(name=str(children[0]))

    def array_type(self, children: list[Any]) -> ArrayType:
        return ArrayType(element_type=str(children[0]), size=int(children[1]))

    def slice_type(self, children: list[Any]) -> SliceType:
        return SliceType(element_type=str(children[0]))

    def result_type(self, children: list[Any]) -> ResultType:
        return ResultType(ok_type=children[0], err_type=children[1])

    def option_type(self, children: list[Any]) -> OptionType:
        return OptionType(inner_type=children[0])

    def ptr_type(self, children: list[Any]) -> PtrType:
        return PtrType(inner_type=children[0], mutable=False)

    def mut_ptr_type(self, children: list[Any]) -> PtrType:
        return PtrType(inner_type=children[0], mutable=True)

    # ------------------------------------------------------------------
    # Contract expressions
    # ------------------------------------------------------------------

    def implication(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="=>", left=children[0], right=children[1])

    def or_op(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="||", left=children[0], right=children[1])

    def and_op(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="&&", left=children[0], right=children[1])

    # Comparison operators
    def gte(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op=">=", left=children[0], right=children[1])

    def lte(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="<=", left=children[0], right=children[1])

    def eq(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="==", left=children[0], right=children[1])

    def neq(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="!=", left=children[0], right=children[1])

    def gt(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op=">", left=children[0], right=children[1])

    def lt(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="<", left=children[0], right=children[1])

    # Arithmetic
    def add(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="+", left=children[0], right=children[1])

    def sub(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="-", left=children[0], right=children[1])

    def mul(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="*", left=children[0], right=children[1])

    def div(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="/", left=children[0], right=children[1])

    def mod(self, children: list[Any]) -> BinaryOp:
        return BinaryOp(op="%", left=children[0], right=children[1])

    # Unary
    def not_op(self, children: list[Any]) -> UnaryOp:
        return UnaryOp(op="!", operand=children[0])

    def neg_op(self, children: list[Any]) -> UnaryOp:
        return UnaryOp(op="-", operand=children[0])

    def addr_op(self, children: list[Any]) -> UnaryOp:
        return UnaryOp(op="&", operand=children[0])

    # Postfix
    def field_access(self, children: list[Any]) -> FieldAccess:
        return FieldAccess(object=children[0], field=str(children[1]))

    def call_expr(self, children: list[Any]) -> CallExpr:
        func = children[0]
        args: tuple = ()
        if len(children) > 1:
            args = children[1]
        return CallExpr(function=func, args=args)

    def index_expr(self, children: list[Any]) -> IndexExpr:
        return IndexExpr(object=children[0], index=children[1])

    # Primary
    def ident(self, children: list[Any]) -> Ident:
        return Ident(name=str(children[0]))

    def number_lit(self, children: list[Any]) -> NumberLit:
        return NumberLit(value=int(children[0]))

    def true_lit(self, _children: list[Any]) -> BoolLit:
        return BoolLit(value=True)

    def false_lit(self, _children: list[Any]) -> BoolLit:
        return BoolLit(value=False)

    def null_lit(self, _children: list[Any]) -> NullLit:
        return NullLit()

    def arg_list(self, children: list[Any]) -> tuple:
        return tuple(children)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_body(raw: str) -> tuple[str, ...]:
    """Extract pseudocode lines from a raw function body string.

    Strips leading ``//`` markers and surrounding whitespace.
    Blank lines are kept as empty strings to preserve structure.
    """
    lines: list[str] = []
    for line in raw.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            stripped = stripped[2:].strip()
        if stripped or lines:
            lines.append(stripped)
    return tuple(lines)
