"""Build LLM prompts from parsed .mcc spec ASTs."""

from __future__ import annotations

from maybecc.parser.ast_nodes import (
    ArrayType,
    BinaryOp,
    BoolLit,
    CallExpr,
    Complexity,
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
    ParamAnnotation,
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
    "u8": "uint8_t",
    "u16": "uint16_t",
    "u32": "uint32_t",
    "u64": "uint64_t",
    "i8": "int8_t",
    "i16": "int16_t",
    "i32": "int32_t",
    "i64": "int64_t",
    "f32": "float",
    "f64": "double",
    "bool": "bool",
    "usize": "size_t",
    "void": "void",
}


def type_to_c(t: TypeExpr) -> str:
    """Convert a spec type expression to its C representation."""
    if isinstance(t, SimpleType):
        return C_TYPE_MAP.get(t.name, t.name)
    if isinstance(t, ArrayType):
        base = C_TYPE_MAP.get(t.element_type, t.element_type)
        return f"{base}[{t.size}]"
    if isinstance(t, SliceType):
        base = C_TYPE_MAP.get(t.element_type, t.element_type)
        return f"const {base}*"
    if isinstance(t, PtrType):
        inner = type_to_c(t.inner_type)
        return f"{inner}*" if t.mutable else f"const {inner}*"
    if isinstance(t, ResultType):
        return f"Result<{type_to_c(t.ok_type)}, {type_to_c(t.err_type)}>"
    if isinstance(t, OptionType):
        return f"Optional<{type_to_c(t.inner_type)}>"
    return str(t)


def expr_to_str(expr: Expr) -> str:
    """Serialize a contract expression back to readable form."""
    if isinstance(expr, Ident):
        return expr.name
    if isinstance(expr, NumberLit):
        return str(expr.value)
    if isinstance(expr, BoolLit):
        return "true" if expr.value else "false"
    if isinstance(expr, NullLit):
        return "NULL"
    if isinstance(expr, BinaryOp):
        left = expr_to_str(expr.left)
        right = expr_to_str(expr.right)
        return f"{left} {expr.op} {right}"
    if isinstance(expr, UnaryOp):
        return f"{expr.op}{expr_to_str(expr.operand)}"
    if isinstance(expr, FieldAccess):
        return f"{expr_to_str(expr.object)}.{expr.field}"
    if isinstance(expr, CallExpr):
        args = ", ".join(expr_to_str(a) for a in expr.args)
        return f"{expr_to_str(expr.function)}({args})"
    if isinstance(expr, IndexExpr):
        return f"{expr_to_str(expr.object)}[{expr_to_str(expr.index)}]"
    return str(expr)


def _format_param(name: str, t: TypeExpr) -> str:
    """Format a parameter for a C function signature."""
    c_type = type_to_c(t)
    if isinstance(t, ArrayType):
        base = C_TYPE_MAP.get(t.element_type, t.element_type)
        return f"{base} {name}[{t.size}]"
    if isinstance(t, SliceType):
        base = C_TYPE_MAP.get(t.element_type, t.element_type)
        return f"const {base}* {name}, size_t {name}_len"
    return f"{c_type} {name}"


def _func_signature(fn: FuncDef) -> str:
    """Build a C function signature string."""
    ret = type_to_c(fn.return_type) if fn.return_type else "void"
    params = ", ".join(_format_param(p.name, p.type) for p in fn.params)
    if not params:
        params = "void"
    return f"{ret} {fn.name}({params})"


def _func_section(fn: FuncDef) -> str:
    """Build the prompt section for one function."""
    lines = [f"### `{_func_signature(fn)}`"]

    for ann in fn.annotations:
        if isinstance(ann, Precondition):
            lines.append(f"- Precondition: {expr_to_str(ann.expr)}")
        elif isinstance(ann, Postcondition):
            lines.append(f"- Postcondition: {expr_to_str(ann.expr)}")
        elif isinstance(ann, Complexity):
            lines.append(f"- Complexity: {ann.text}")
        elif isinstance(ann, FlagAnnotation):
            lines.append(f"- Constraint: @{ann.name}")
        elif isinstance(ann, ParamAnnotation):
            lines.append(f"- @{ann.name}(...)")

    if fn.body:
        lines.append("")
        lines.append("Implementation guide:")
        for step in fn.body:
            lines.append(f"- {step}")

    return "\n".join(lines)


def build_prompt(module: Module, target: str | None = None) -> str:
    """Build a code generation prompt from a parsed .mcc module."""
    if target is None:
        for d in module.directives:
            if d.name == "target":
                target = d.args[0].value if d.args else "c99"
                break
        else:
            target = "c99"

    sections = [
        "You are generating C code from a formal specification.",
        f"Generate a SINGLE, complete, compilable C source file targeting {target}.",
        "",
    ]

    if module.structs:
        sections.append("## Type Definitions")
        for s in module.structs:
            fields = ", ".join(
                f"{type_to_c(f.type)} {f.name}" for f in s.fields
            )
            sections.append(f"- struct {s.name} {{ {fields} }}")
        sections.append("")

    if module.enums:
        sections.append("## Enumerations")
        for e in module.enums:
            variants = ", ".join(e.variants)
            sections.append(f"- enum {e.name} {{ {variants} }}")
        sections.append("")

    sections.append("## Functions to Implement")
    sections.append("")
    for fn in module.functions:
        sections.append(_func_section(fn))
        sections.append("")

    sections.extend([
        "## Requirements",
        "",
        f"1. Output ONLY a single C source file inside a ```c code block",
        f"2. Include all necessary headers (stdint.h, stdio.h, stdlib.h, stdbool.h, etc.)",
        f"3. Implement each function exactly matching the specified signature",
        f"4. Include a main() function that:",
        f"   - Tests each function with representative inputs",
        f"   - Prints results in the format: function_name(args) = result",
        f"   - Returns 0 on success",
        f"5. Must compile cleanly with: cc -Wall -Werror -std={target}",
        f"6. Check preconditions where appropriate",
        f"7. Do NOT include any text outside the code block",
    ])

    return "\n".join(sections)


def build_retry_prompt(
    module: Module,
    previous_code: str,
    error_output: str,
    target: str | None = None,
) -> str:
    """Build a retry prompt including the previous failed attempt and error."""
    base = build_prompt(module, target)
    return "\n".join([
        base,
        "",
        "## Previous Attempt (FAILED)",
        "",
        "The following code was generated but failed compilation or verification:",
        "",
        "```c",
        previous_code,
        "```",
        "",
        "## Error Output",
        "",
        "```",
        error_output,
        "```",
        "",
        "Fix the specific errors above and generate a corrected version.",
        "Output ONLY the corrected C source file in a ```c code block.",
    ])
