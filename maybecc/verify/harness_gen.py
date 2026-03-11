"""Generate C test harnesses from .mcc contract specifications.

Converts preconditions into runtime guards and postconditions into
assertions.  Test inputs are generated from type-based representative
values and filtered against preconditions at runtime.
"""

from __future__ import annotations

import itertools
from typing import Sequence

from maybecc.parser.ast_nodes import (
    ArrayType,
    BinaryOp,
    BoolLit,
    CallExpr,
    Expr,
    FieldAccess,
    FlagAnnotation,
    FuncDef,
    Ident,
    IndexExpr,
    Module,
    NullLit,
    NumberLit,
    OptionType,
    Param,
    Postcondition,
    Precondition,
    PtrType,
    ResultType,
    SimpleType,
    SliceType,
    TypeExpr,
    UnaryOp,
)

C_TYPE_MAP = {
    "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
    "i8": "int8_t", "i16": "int16_t", "i32": "int32_t", "i64": "int64_t",
    "f32": "float", "f64": "double",
    "bool": "bool", "usize": "size_t", "void": "void",
}

_TEST_VALUES: dict[str, list[str]] = {
    "u8":  ["0", "1", "127", "255"],
    "u16": ["0", "1", "1000", "65535"],
    "u32": ["0", "1", "42", "100", "1000"],
    "u64": ["0", "1", "42", "100000"],
    "i8":  ["0", "1", "-1", "127", "-128"],
    "i16": ["0", "1", "-1", "1000", "-1000"],
    "i32": ["0", "1", "-1", "42", "-42", "1000"],
    "i64": ["0", "1", "-1", "42", "-42"],
    "f32": ["0.0f", "1.0f", "-1.0f", "3.14f"],
    "f64": ["0.0", "1.0", "-1.0", "3.14159"],
    "bool": ["true", "false"],
    "usize": ["0", "1", "42", "1024"],
}

MAX_COMBINATIONS = 64


def expr_to_c(expr: Expr) -> str:
    """Convert a contract expression AST node to C source code."""
    if isinstance(expr, Ident):
        return expr.name
    if isinstance(expr, NumberLit):
        return str(expr.value)
    if isinstance(expr, BoolLit):
        return "true" if expr.value else "false"
    if isinstance(expr, NullLit):
        return "NULL"
    if isinstance(expr, BinaryOp):
        left, right = expr_to_c(expr.left), expr_to_c(expr.right)
        if expr.op == "=>":
            return f"(!({left}) || ({right}))"
        return f"({left} {expr.op} {right})"
    if isinstance(expr, UnaryOp):
        return f"({expr.op}({expr_to_c(expr.operand)}))"
    if isinstance(expr, FieldAccess):
        obj = expr_to_c(expr.object)
        if "->" in obj or obj.startswith("(*"):
            return f"{obj}->{expr.field}"
        return f"{obj}.{expr.field}"
    if isinstance(expr, CallExpr):
        func = expr_to_c(expr.function)
        args = ", ".join(expr_to_c(a) for a in expr.args)
        return f"{func}({args})"
    if isinstance(expr, IndexExpr):
        return f"{expr_to_c(expr.object)}[{expr_to_c(expr.index)}]"
    return str(expr)


def type_to_c(t: TypeExpr) -> str:
    """Map a spec type to its C representation."""
    if isinstance(t, SimpleType):
        return C_TYPE_MAP.get(t.name, t.name)
    if isinstance(t, PtrType):
        inner = type_to_c(t.inner_type)
        return f"{inner}*"
    return C_TYPE_MAP.get(str(t), str(t))


def _is_simple_type(t: TypeExpr) -> bool:
    """True if the type maps to a plain C scalar we can generate test values for."""
    return isinstance(t, SimpleType) and t.name in _TEST_VALUES


def _is_testable(fn: FuncDef) -> bool:
    """True if we can auto-generate contract tests for this function."""
    if not fn.params:
        return True
    if not all(_is_simple_type(p.type) for p in fn.params):
        return False
    if fn.return_type and isinstance(fn.return_type, (ResultType, OptionType)):
        return False
    return True


def _test_values_for(param: Param) -> list[str]:
    if isinstance(param.type, SimpleType) and param.type.name in _TEST_VALUES:
        return _TEST_VALUES[param.type.name]
    return ["0"]


def _generate_test_func(fn: FuncDef) -> list[str]:
    """Generate a test function for one spec function."""
    lines: list[str] = []
    fname = fn.name
    ret_c = type_to_c(fn.return_type) if fn.return_type else "void"
    is_void = ret_c == "void"

    preconditions = [a for a in fn.annotations if isinstance(a, Precondition)]
    postconditions = [a for a in fn.annotations if isinstance(a, Postcondition)]

    param_values = [_test_values_for(p) for p in fn.params]
    combos = list(itertools.islice(itertools.product(*param_values), MAX_COMBINATIONS))

    lines.append(f"static int test_{fname}(void) {{")
    lines.append(f"    int _mcc_passed = 0;")

    if not combos:
        combos = [()]

    for idx, combo in enumerate(combos):
        lines.append("    {")
        for param, val in zip(fn.params, combo):
            c_type = type_to_c(param.type)
            lines.append(f"        {c_type} {param.name} = {val};")

        if preconditions:
            guards = " && ".join(f"({expr_to_c(p.expr)})" for p in preconditions)
            lines.append(f"        if (!({guards})) goto _mcc_skip_{fname}_{idx};")

        call_args = ", ".join(p.name for p in fn.params)
        if is_void:
            lines.append(f"        {fname}({call_args});")
        else:
            lines.append(f"        {ret_c} result = {fname}({call_args});")
            if not postconditions:
                lines.append(f"        (void)result;")

        for post in postconditions:
            c_expr = expr_to_c(post.expr)
            lines.append(f"        if (!({c_expr})) {{")
            escaped = c_expr.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'            fprintf(stderr, "FAIL: {fname}: postcondition violated: {escaped}\\n");')
            lines.append(f"            return 1;")
            lines.append(f"        }}")

        lines.append(f"        _mcc_passed++;")
        if preconditions:
            lines.append(f"        _mcc_skip_{fname}_{idx}: ;")
        lines.append("    }")

    lines.append(f'    fprintf(stderr, "{fname}: %d test cases passed\\n", _mcc_passed);')
    lines.append(f"    return 0;")
    lines.append("}")
    return lines


def generate_test_harness(module: Module, source_filename: str) -> str:
    """Generate a complete C test harness for a module's contracts.

    The harness ``#include``s the generated source (renaming its ``main``
    to avoid conflicts) and runs contract tests for every testable function.
    """
    testable = [fn for fn in module.functions if _is_testable(fn)]
    if not testable:
        return ""

    lines: list[str] = [
        "/* Auto-generated contract test harness — do not edit */",
        "#define main _mcc_original_main",
        f'#include "{source_filename}"',
        "#undef main",
        "",
        "#include <stdio.h>",
        "#include <assert.h>",
        "#include <stdint.h>",
        "#include <stdbool.h>",
        "#include <string.h>",
        "",
    ]

    for fn in testable:
        lines.extend(_generate_test_func(fn))
        lines.append("")

    lines.append("int main(void) {")
    lines.append("    int _mcc_fail = 0;")
    for fn in testable:
        lines.append(f"    _mcc_fail |= test_{fn.name}();")
    lines.append('    if (!_mcc_fail) fprintf(stderr, "All contract tests passed.\\n");')
    lines.append("    return _mcc_fail;")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)
