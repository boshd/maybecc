# maybecc

A non-deterministic compiler that uses LLMs as a code generation oracle with deterministic verification.

## Core thesis

Compilation from a spec language to C follows the structure of a non-deterministic Turing machine.
The LLM acts as the non-deterministic oracle (guessing a valid program from the space of all
possible implementations), and deterministic verification (type checking, sanitizers, fuzzing,
property-based testing) confirms whether the guess satisfies the spec.

## Quick start

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY="sk-ant-..."

# Compile a spec to verified C and run it
maybecc compile examples/calculator.mcc -o build/ --run --verbose

# Parse a spec without generating code
maybecc parse examples/packet_parser.mcc

# Run the parser test suite
pytest
```

## How it works

```
  .mcc spec ──> Parser ──> AST ──> Prompt Builder ──> LLM (Claude)
                                                          │
                                                     C source code
                                                          │
                            ┌──────────────────────────── ▼
                            │         Verification Pipeline
                            │  ┌─────────────────────────────────┐
                            │  │ 1. Compile with sanitizers       │
                            │  │ 2. Run (LLM-generated tests)    │
                            │  │ 3. Contract test harness         │
                            │  │ 4. Fuzz harness (if configured)  │
                            │  └─────────────────────────────────┘
                            │              │           │
                            │           pass?       fail?
                            │              │           │
                            │         emit binary    retry with
                            │         + report       error feedback
                            └──────────────────────────┘
```

On each failure, the error output (compiler errors, assertion failures, sanitizer
reports, fuzz crashes) is fed back to the LLM along with the original spec.
Temperature increases on each retry to explore more of the solution space.

## Verification layers

| Layer | What it catches | Triggered by |
|---|---|---|
| Compilation (`-Wall -Werror`) | Type errors, missing includes, undefined symbols | Always |
| AddressSanitizer | Buffer overflows, use-after-free, memory leaks | `@verify(asan)` or `@no_undefined_behavior` |
| UndefinedBehaviorSanitizer | Signed overflow, null deref, shift bugs | `@verify(ubsan)` or `@no_undefined_behavior` |
| Contract tests | Postcondition violations on representative inputs | Any `@post(...)` annotation |
| Fuzz harness | Crashes and postcondition violations on random inputs | `@verify(fuzz: N)` |

## Example specs

- `examples/calculator.mcc` — simple arithmetic, good for first test
- `examples/packet_parser.mcc` — binary parsing with checksums
- `examples/ring_buffer.mcc` — pointer-heavy circular buffer
- `examples/linked_list.mcc` — intrusive doubly-linked list
- `examples/base64_codec.mcc` — encode/decode with roundtrip properties

## Project status

All four phases are implemented:

1. **Parser** — Lark LALR grammar, typed AST, 60 tests
2. **Codegen** — prompt builder, Anthropic API client, C code extraction
3. **Verification** — compilation with sanitizers, contract test harness generation, fuzz harness generation
4. **Orchestration** — retry loop with error feedback, verification report generation
