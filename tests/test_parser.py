"""Comprehensive tests for the .mcc parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from maybecc.parser import (
    ArrayType,
    BinaryOp,
    BoolLit,
    CallExpr,
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
    parse,
)
from maybecc.parser.preprocessor import preprocess

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# ======================================================================
# Preprocessor tests
# ======================================================================


class TestPreprocessor:
    def test_extracts_function_body(self):
        source = 'fn foo(x: u32) -> u32 { // do stuff }'
        result = preprocess(source)
        assert "__BODY_0__" in result.source
        assert len(result.bodies) == 1
        assert "do stuff" in result.bodies[0]

    def test_preserves_struct_braces(self):
        source = 'struct Foo { x: u32 }'
        result = preprocess(source)
        assert "__BODY_" not in result.source
        assert "{" in result.source
        assert len(result.bodies) == 0

    def test_preserves_enum_braces(self):
        source = 'enum E { A, B, C }'
        result = preprocess(source)
        assert "__BODY_" not in result.source
        assert len(result.bodies) == 0

    def test_multiple_functions(self):
        source = """
fn foo() { // body one }
fn bar() { // body two }
"""
        result = preprocess(source)
        assert len(result.bodies) == 2
        assert "body one" in result.bodies[0]
        assert "body two" in result.bodies[1]

    def test_extracts_complexity(self):
        source = '@complexity(O(n) where n = x.len)'
        result = preprocess(source)
        assert "__CMPLX_0__" in result.source
        assert len(result.complexities) == 1
        assert result.complexities[0] == "O(n) where n = x.len"

    def test_complexity_with_nested_parens(self):
        source = '@complexity(O(n * log(n)))'
        result = preprocess(source)
        assert result.complexities[0] == "O(n * log(n))"

    def test_mixed_extraction(self):
        source = """
struct S { x: u32 }
fn foo(x: u32) -> u32
  @complexity(O(1))
{
  // return x
}
"""
        result = preprocess(source)
        assert len(result.bodies) == 1
        assert len(result.complexities) == 1
        assert result.complexities[0] == "O(1)"
        assert "return x" in result.bodies[0]

    def test_unmatched_brace_raises(self):
        source = 'fn foo() { // unclosed'
        with pytest.raises(SyntaxError, match="Unmatched"):
            preprocess(source)


# ======================================================================
# Directive parsing
# ======================================================================


class TestDirectives:
    def test_target_directive(self):
        module = parse('@target(c99)')
        assert len(module.directives) == 1
        d = module.directives[0]
        assert d.name == "target"
        assert d.args == (PositionalArg(value="c99"),)

    def test_verify_directive_with_keyed_and_positional(self):
        module = parse('@verify(fuzz: 10000, asan, ubsan)')
        d = module.directives[0]
        assert d.args[0] == KeyedArg(key="fuzz", value=10000)
        assert d.args[1] == PositionalArg(value="asan")
        assert d.args[2] == PositionalArg(value="ubsan")

    def test_multiple_directives(self):
        module = parse('@target(c99)\n@verify(asan)')
        assert len(module.directives) == 2


# ======================================================================
# Struct parsing
# ======================================================================


class TestStructs:
    def test_simple_struct(self):
        module = parse("""
struct Point {
  x: f32
  y: f32
}
""")
        assert len(module.structs) == 1
        s = module.structs[0]
        assert s.name == "Point"
        assert len(s.fields) == 2
        assert s.fields[0] == Field(name="x", type=SimpleType(name="f32"))
        assert s.fields[1] == Field(name="y", type=SimpleType(name="f32"))

    def test_struct_with_array_and_slice_types(self):
        module = parse("""
struct Packet {
  header: bytes[12]
  payload: bytes[..]
  checksum: u32
}
""")
        s = module.structs[0]
        assert s.fields[0].type == ArrayType(element_type="bytes", size=12)
        assert s.fields[1].type == SliceType(element_type="bytes")
        assert s.fields[2].type == SimpleType(name="u32")

    def test_struct_with_pointer_field(self):
        module = parse("struct Buf { data: *mut u8  len: usize }")
        s = module.structs[0]
        assert s.fields[0].type == PtrType(inner_type=SimpleType(name="u8"), mutable=True)


# ======================================================================
# Enum parsing
# ======================================================================


class TestEnums:
    def test_simple_enum(self):
        module = parse("enum Color { Red, Green, Blue }")
        assert len(module.enums) == 1
        e = module.enums[0]
        assert e.name == "Color"
        assert e.variants == ("Red", "Green", "Blue")

    def test_enum_multiline(self):
        module = parse("""
enum ParseError {
  TooShort,
  ChecksumMismatch,
  InvalidLength
}
""")
        e = module.enums[0]
        assert e.variants == ("TooShort", "ChecksumMismatch", "InvalidLength")


# ======================================================================
# Type expression parsing
# ======================================================================


class TestTypes:
    def test_simple_type(self):
        module = parse("struct T { x: u32 }")
        assert module.structs[0].fields[0].type == SimpleType(name="u32")

    def test_array_type(self):
        module = parse("struct T { x: u8[16] }")
        assert module.structs[0].fields[0].type == ArrayType(element_type="u8", size=16)

    def test_slice_type(self):
        module = parse("struct T { x: u8[..] }")
        assert module.structs[0].fields[0].type == SliceType(element_type="u8")

    def test_result_type(self):
        module = parse("fn f() -> Result<u32, Error> { // x }")
        fn = module.functions[0]
        assert fn.return_type == ResultType(
            ok_type=SimpleType(name="u32"),
            err_type=SimpleType(name="Error"),
        )

    def test_option_type(self):
        module = parse("fn f() -> Option<u8> { // x }")
        fn = module.functions[0]
        assert fn.return_type == OptionType(inner_type=SimpleType(name="u8"))

    def test_const_ptr_type(self):
        module = parse("struct T { p: *u8 }")
        assert module.structs[0].fields[0].type == PtrType(
            inner_type=SimpleType(name="u8"), mutable=False
        )

    def test_mut_ptr_type(self):
        module = parse("struct T { p: *mut u8 }")
        assert module.structs[0].fields[0].type == PtrType(
            inner_type=SimpleType(name="u8"), mutable=True
        )

    def test_nested_result_option(self):
        module = parse("fn f() -> Result<Option<u32>, Error> { // x }")
        fn = module.functions[0]
        assert fn.return_type == ResultType(
            ok_type=OptionType(inner_type=SimpleType(name="u32")),
            err_type=SimpleType(name="Error"),
        )


# ======================================================================
# Function parsing
# ======================================================================


class TestFunctions:
    def test_minimal_function(self):
        module = parse("fn noop() { // nothing }")
        assert len(module.functions) == 1
        fn = module.functions[0]
        assert fn.name == "noop"
        assert fn.params == ()
        assert fn.return_type is None
        assert fn.annotations == ()
        assert fn.body == ("nothing",)

    def test_function_with_params(self):
        module = parse("fn add(a: i32, b: i32) -> i32 { // return a + b }")
        fn = module.functions[0]
        assert fn.params == (
            Param(name="a", type=SimpleType(name="i32")),
            Param(name="b", type=SimpleType(name="i32")),
        )
        assert fn.return_type == SimpleType(name="i32")

    def test_function_body_multiline(self):
        module = parse("""
fn work() {
  // step one
  // step two
  // step three
}
""")
        fn = module.functions[0]
        assert fn.body == ("step one", "step two", "step three")

    def test_void_return(self):
        module = parse("fn cleanup() -> void { // free resources }")
        fn = module.functions[0]
        assert fn.return_type == SimpleType(name="void")


# ======================================================================
# Annotation parsing
# ======================================================================


class TestAnnotations:
    def test_precondition(self):
        module = parse("fn f(x: u32) @pre(x > 0) { // body }")
        fn = module.functions[0]
        assert len(fn.annotations) == 1
        pre = fn.annotations[0]
        assert isinstance(pre, Precondition)
        assert pre.expr == BinaryOp(
            op=">", left=Ident(name="x"), right=NumberLit(value=0)
        )

    def test_postcondition(self):
        module = parse("fn f() -> u32 @post(result > 0) { // body }")
        fn = module.functions[0]
        post = fn.annotations[0]
        assert isinstance(post, Postcondition)

    def test_complexity_annotation(self):
        module = parse("fn f(x: u32[..]) @complexity(O(n) where n = x.len) { // body }")
        fn = module.functions[0]
        cmplx = fn.annotations[0]
        assert isinstance(cmplx, Complexity)
        assert cmplx.text == "O(n) where n = x.len"

    def test_flag_annotation(self):
        module = parse("fn f() @no_undefined_behavior { // body }")
        fn = module.functions[0]
        flag = fn.annotations[0]
        assert isinstance(flag, FlagAnnotation)
        assert flag.name == "no_undefined_behavior"

    def test_parameterized_annotation(self):
        module = parse("fn f() @verify(asan, ubsan) { // body }")
        fn = module.functions[0]
        ann = fn.annotations[0]
        assert isinstance(ann, ParamAnnotation)
        assert ann.name == "verify"
        assert ann.args == (
            PositionalArg(value="asan"),
            PositionalArg(value="ubsan"),
        )

    def test_multiple_annotations(self):
        module = parse("""
fn f(x: u32) -> u32
  @pre(x > 0)
  @post(result >= x)
  @no_undefined_behavior
{
  // body
}
""")
        fn = module.functions[0]
        assert len(fn.annotations) == 3
        assert isinstance(fn.annotations[0], Precondition)
        assert isinstance(fn.annotations[1], Postcondition)
        assert isinstance(fn.annotations[2], FlagAnnotation)


# ======================================================================
# Expression parsing (contract language)
# ======================================================================


class TestExpressions:
    def _parse_pre(self, expr_str: str):
        module = parse(f"fn f() @pre({expr_str}) {{ // body }}")
        return module.functions[0].annotations[0].expr

    def test_simple_comparison(self):
        expr = self._parse_pre("x >= 16")
        assert expr == BinaryOp(
            op=">=", left=Ident(name="x"), right=NumberLit(value=16)
        )

    def test_field_access_chain(self):
        expr = self._parse_pre("a.b.c >= 0")
        assert expr.left == FieldAccess(
            object=FieldAccess(object=Ident(name="a"), field="b"),
            field="c",
        )

    def test_function_call(self):
        expr = self._parse_pre("crc32(x) == 42")
        assert expr.left == CallExpr(
            function=Ident(name="crc32"), args=(Ident(name="x"),)
        )

    def test_function_call_multiple_args(self):
        expr = self._parse_pre("f(a, b, c) == 0")
        call = expr.left
        assert isinstance(call, CallExpr)
        assert len(call.args) == 3

    def test_implication(self):
        expr = self._parse_pre("a => b")
        assert expr == BinaryOp(
            op="=>", left=Ident(name="a"), right=Ident(name="b")
        )

    def test_implication_right_associative(self):
        expr = self._parse_pre("a => b => c")
        assert expr == BinaryOp(
            op="=>",
            left=Ident(name="a"),
            right=BinaryOp(
                op="=>", left=Ident(name="b"), right=Ident(name="c")
            ),
        )

    def test_logical_and(self):
        expr = self._parse_pre("a && b")
        assert expr == BinaryOp(
            op="&&", left=Ident(name="a"), right=Ident(name="b")
        )

    def test_logical_or(self):
        expr = self._parse_pre("a || b")
        assert expr == BinaryOp(
            op="||", left=Ident(name="a"), right=Ident(name="b")
        )

    def test_not(self):
        expr = self._parse_pre("!x")
        assert expr == UnaryOp(op="!", operand=Ident(name="x"))

    def test_negation(self):
        expr = self._parse_pre("-x > 0")
        assert expr.left == UnaryOp(op="-", operand=Ident(name="x"))

    def test_bool_literals(self):
        assert self._parse_pre("true") == BoolLit(value=True)
        assert self._parse_pre("false") == BoolLit(value=False)

    def test_parenthesized_expression(self):
        expr = self._parse_pre("(a || b) && c")
        assert expr == BinaryOp(
            op="&&",
            left=BinaryOp(op="||", left=Ident(name="a"), right=Ident(name="b")),
            right=Ident(name="c"),
        )

    def test_precedence_and_or(self):
        # && binds tighter than ||
        expr = self._parse_pre("a || b && c")
        assert expr == BinaryOp(
            op="||",
            left=Ident(name="a"),
            right=BinaryOp(
                op="&&", left=Ident(name="b"), right=Ident(name="c")
            ),
        )

    def test_arithmetic_add_sub(self):
        expr = self._parse_pre("a + b - c >= 0")
        lhs = expr.left
        assert lhs == BinaryOp(
            op="-",
            left=BinaryOp(
                op="+", left=Ident(name="a"), right=Ident(name="b")
            ),
            right=Ident(name="c"),
        )

    def test_arithmetic_mul_div(self):
        expr = self._parse_pre("a * b / c > 0")
        lhs = expr.left
        assert lhs == BinaryOp(
            op="/",
            left=BinaryOp(
                op="*", left=Ident(name="a"), right=Ident(name="b")
            ),
            right=Ident(name="c"),
        )

    def test_modulo(self):
        expr = self._parse_pre("x % 4 == 0")
        assert expr.left == BinaryOp(
            op="%", left=Ident(name="x"), right=NumberLit(value=4)
        )

    def test_index_expression(self):
        expr = self._parse_pre("arr[0] == 42")
        assert expr.left == IndexExpr(
            object=Ident(name="arr"), index=NumberLit(value=0)
        )

    def test_complex_postcondition(self):
        """The signature contract from the packet_parser example."""
        expr = self._parse_pre(
            "result.ok => result.value.checksum == crc32(result.value.payload)"
        )
        assert isinstance(expr, BinaryOp)
        assert expr.op == "=>"

        lhs = expr.left
        assert lhs == FieldAccess(object=Ident(name="result"), field="ok")

        rhs = expr.right
        assert isinstance(rhs, BinaryOp)
        assert rhs.op == "=="
        assert rhs.left == FieldAccess(
            object=FieldAccess(object=Ident(name="result"), field="value"),
            field="checksum",
        )
        assert rhs.right == CallExpr(
            function=Ident(name="crc32"),
            args=(
                FieldAccess(
                    object=FieldAccess(
                        object=Ident(name="result"), field="value"
                    ),
                    field="payload",
                ),
            ),
        )

    def test_all_comparison_ops(self):
        for op in ["==", "!=", ">=", "<=", ">", "<"]:
            expr = self._parse_pre(f"a {op} b")
            assert expr == BinaryOp(
                op=op, left=Ident(name="a"), right=Ident(name="b")
            )


# ======================================================================
# Full example file tests
# ======================================================================


class TestExampleFiles:
    def test_packet_parser(self):
        source = (EXAMPLES_DIR / "packet_parser.mcc").read_text()
        module = parse(source)

        assert len(module.directives) == 2
        assert module.directives[0].name == "target"
        assert module.directives[1].name == "verify"

        assert len(module.enums) == 1
        assert module.enums[0].name == "ParseError"
        assert "TooShort" in module.enums[0].variants
        assert "ChecksumMismatch" in module.enums[0].variants

        assert len(module.structs) == 1
        assert module.structs[0].name == "Packet"

        assert len(module.functions) >= 1
        fn = module.functions[0]
        assert fn.name == "parse_packet"
        assert fn.return_type == ResultType(
            ok_type=SimpleType(name="Packet"),
            err_type=SimpleType(name="ParseError"),
        )
        assert any(isinstance(a, Precondition) for a in fn.annotations)
        assert any(isinstance(a, Postcondition) for a in fn.annotations)

    def test_ring_buffer(self):
        source = (EXAMPLES_DIR / "ring_buffer.mcc").read_text()
        module = parse(source)

        assert len(module.structs) == 1
        assert module.structs[0].name == "RingBuffer"
        assert len(module.structs[0].fields) == 5

        assert len(module.functions) == 4
        fn_names = [f.name for f in module.functions]
        assert fn_names == [
            "ring_buffer_create",
            "ring_buffer_push",
            "ring_buffer_pop",
            "ring_buffer_destroy",
        ]

        push_fn = module.functions[1]
        assert push_fn.params[0].type == PtrType(
            inner_type=SimpleType(name="RingBuffer"), mutable=True
        )

    def test_base64_codec(self):
        source = (EXAMPLES_DIR / "base64_codec.mcc").read_text()
        module = parse(source)

        assert len(module.enums) == 1
        assert module.enums[0].name == "Base64Error"

        assert len(module.functions) == 3
        fn_names = [f.name for f in module.functions]
        assert fn_names == [
            "base64_encode_len",
            "base64_encode",
            "base64_decode",
        ]

        decode_fn = module.functions[2]
        assert any(
            isinstance(a, Precondition)
            and isinstance(a.expr, BinaryOp)
            and a.expr.op == "=="
            for a in decode_fn.annotations
        )


# ======================================================================
# Error handling
# ======================================================================


class TestErrors:
    def test_syntax_error_raises(self):
        with pytest.raises(Exception):
            parse("fn 123invalid() { // body }")

    def test_unclosed_brace_raises(self):
        with pytest.raises(SyntaxError):
            parse("fn foo() { // no close")

    def test_empty_input(self):
        module = parse("")
        assert module == Module(
            directives=(), structs=(), enums=(), functions=()
        )

    def test_whitespace_only(self):
        module = parse("   \n\n   \n")
        assert module == Module(
            directives=(), structs=(), enums=(), functions=()
        )
