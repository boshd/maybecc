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

# Parse a spec file
python -c "from maybecc.parser import parse; print(parse(open('examples/packet_parser.mcc').read()))"

# Run tests
pytest
```

## Usage

```bash
maybecc compile examples/packet_parser.mcc -o build/
```

## Project status

Phase 1 (parser) is implemented. Phases 2-4 (codegen, verification, orchestration) are stubbed.
