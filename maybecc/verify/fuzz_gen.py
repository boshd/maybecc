"""Generate libFuzzer harnesses from .mcc specifications.

For each function with ``@verify(fuzz: N)``, generates a
``LLVMFuzzerTestOneInput`` entry point that reads random bytes,
interprets them as function parameters, checks preconditions,
calls the function, and asserts postconditions.
"""

from __future__ import annotations

from maybecc.parser.ast_nodes import (
    FuncDef,
    Module,
    OptionType,
    Param,
    Postcondition,
    Precondition,
    PtrType,
    ResultType,
    SimpleType,
    TypeExpr,
)
from maybecc.verify.harness_gen import C_TYPE_MAP, expr_to_c, type_to_c

_SIZEOF: dict[str, int] = {
    "u8": 1, "i8": 1, "bool": 1,
    "u16": 2, "i16": 2,
    "u32": 4, "i32": 4, "f32": 4,
    "u64": 8, "i64": 8, "f64": 8,
    "usize": 8,
}


def _param_size(t: TypeExpr) -> int | None:
    if isinstance(t, SimpleType) and t.name in _SIZEOF:
        return _SIZEOF[t.name]
    return None


def _is_fuzzable(fn: FuncDef) -> bool:
    """True if all parameters are fixed-size scalars we can deserialize from fuzz data."""
    if not fn.params:
        return False
    return all(_param_size(p.type) is not None for p in fn.params)


def _generate_fuzz_func(fn: FuncDef) -> list[str]:
    """Generate a LLVMFuzzerTestOneInput for one function."""
    total_size = sum(_param_size(p.type) for p in fn.params)
    ret_c = type_to_c(fn.return_type) if fn.return_type else "void"
    is_void = ret_c == "void"

    preconditions = [a for a in fn.annotations if isinstance(a, Precondition)]
    postconditions = [a for a in fn.annotations if isinstance(a, Postcondition)]

    lines: list[str] = []
    lines.append("int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {")
    lines.append(f"    if (size < {total_size}) return 0;")
    lines.append("")

    offset = 0
    for p in fn.params:
        c_type = type_to_c(p.type)
        sz = _param_size(p.type)
        lines.append(f"    {c_type} {p.name};")
        lines.append(f"    memcpy(&{p.name}, data + {offset}, {sz});")
        offset += sz
    lines.append("")

    if preconditions:
        guards = " && ".join(f"({expr_to_c(p.expr)})" for p in preconditions)
        lines.append(f"    if (!({guards})) return 0;")
        lines.append("")

    call_args = ", ".join(p.name for p in fn.params)
    if is_void:
        lines.append(f"    {fn.name}({call_args});")
    else:
        lines.append(f"    {ret_c} result = {fn.name}({call_args});")

    if postconditions:
        lines.append("")
    for post in postconditions:
        c_expr = expr_to_c(post.expr)
        lines.append(f"    assert({c_expr});")

    lines.append("")
    lines.append("    return 0;")
    lines.append("}")
    return lines


def generate_fuzz_harness(module: Module, source_filename: str) -> str:
    """Generate a libFuzzer harness covering fuzzable functions.

    Returns an empty string if no functions are fuzzable.
    """
    fuzzable = [fn for fn in module.functions if _is_fuzzable(fn)]
    if not fuzzable:
        return ""

    fn = fuzzable[0]

    lines: list[str] = [
        "/* Auto-generated libFuzzer harness — do not edit */",
        "#define main _mcc_original_main",
        f'#include "{source_filename}"',
        "#undef main",
        "",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "#include <string.h>",
        "#include <assert.h>",
        "",
    ]

    lines.extend(_generate_fuzz_func(fn))
    lines.append("")
    return "\n".join(lines)
