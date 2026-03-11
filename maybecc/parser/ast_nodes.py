"""Typed AST node definitions for the .mcc spec language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


# ---------------------------------------------------------------------------
# Type nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimpleType:
    name: str


@dataclass(frozen=True)
class ArrayType:
    element_type: str
    size: int


@dataclass(frozen=True)
class SliceType:
    element_type: str


@dataclass(frozen=True)
class ResultType:
    ok_type: TypeExpr
    err_type: TypeExpr


@dataclass(frozen=True)
class OptionType:
    inner_type: TypeExpr


@dataclass(frozen=True)
class PtrType:
    inner_type: TypeExpr
    mutable: bool = False


TypeExpr = Union[SimpleType, ArrayType, SliceType, ResultType, OptionType, PtrType]


# ---------------------------------------------------------------------------
# Expression nodes (used in contract pre/post conditions)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ident:
    name: str


@dataclass(frozen=True)
class NumberLit:
    value: int


@dataclass(frozen=True)
class BoolLit:
    value: bool


@dataclass(frozen=True)
class NullLit:
    pass


@dataclass(frozen=True)
class BinaryOp:
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: Expr


@dataclass(frozen=True)
class FieldAccess:
    object: Expr
    field: str


@dataclass(frozen=True)
class CallExpr:
    function: Expr
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class IndexExpr:
    object: Expr
    index: Expr


Expr = Union[
    Ident, NumberLit, BoolLit, NullLit, BinaryOp, UnaryOp,
    FieldAccess, CallExpr, IndexExpr,
]


# ---------------------------------------------------------------------------
# Directive / annotation argument nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeyedArg:
    key: str
    value: str | int


@dataclass(frozen=True)
class PositionalArg:
    value: str | int


DirectiveArg = Union[KeyedArg, PositionalArg]


# ---------------------------------------------------------------------------
# Annotation nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Precondition:
    expr: Expr


@dataclass(frozen=True)
class Postcondition:
    expr: Expr


@dataclass(frozen=True)
class Complexity:
    text: str


@dataclass(frozen=True)
class FlagAnnotation:
    name: str


@dataclass(frozen=True)
class ParamAnnotation:
    name: str
    args: tuple[DirectiveArg, ...]


Annotation = Union[
    Precondition, Postcondition, Complexity, FlagAnnotation, ParamAnnotation,
]


# ---------------------------------------------------------------------------
# Definition nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    name: str
    type: TypeExpr


@dataclass(frozen=True)
class Param:
    name: str
    type: TypeExpr


@dataclass(frozen=True)
class StructDef:
    name: str
    fields: tuple[Field, ...]


@dataclass(frozen=True)
class EnumDef:
    name: str
    variants: tuple[str, ...]


@dataclass(frozen=True)
class Directive:
    name: str
    args: tuple[DirectiveArg, ...]


@dataclass(frozen=True)
class FuncDef:
    name: str
    params: tuple[Param, ...]
    return_type: TypeExpr | None
    annotations: tuple[Annotation, ...]
    body: tuple[str, ...]


# ---------------------------------------------------------------------------
# Top-level module
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Module:
    directives: tuple[Directive, ...]
    structs: tuple[StructDef, ...]
    enums: tuple[EnumDef, ...]
    functions: tuple[FuncDef, ...]
