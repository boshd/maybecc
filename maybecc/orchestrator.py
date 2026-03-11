"""Main pipeline: parse -> generate -> compile -> retry."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from maybecc.codegen.extractor import extract_c_source
from maybecc.codegen.llm_client import generate_code
from maybecc.codegen.prompt_builder import build_prompt, build_retry_prompt
from maybecc.parser.parser import parse_file


@dataclass
class CompileResult:
    success: bool
    source_path: Path | None = None
    binary_path: Path | None = None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)


def run(
    spec_path: str,
    output_dir: str = "build",
    max_retries: int = 5,
    model: str = "claude-sonnet-4-20250514",
    verbose: bool = False,
    log=print,
) -> CompileResult:
    """Run the full pipeline: parse spec, generate C, compile, retry on failure."""
    from maybecc.verify.compiler import compile_c

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    spec = Path(spec_path)
    stem = spec.stem

    log(f"Parsing {spec_path}...")
    module = parse_file(spec_path)
    n_fns = len(module.functions)
    n_structs = len(module.structs)
    n_enums = len(module.enums)
    log(f"  {n_fns} function(s), {n_structs} struct(s), {n_enums} enum(s)")

    target = "c99"
    for d in module.directives:
        if d.name == "target" and d.args:
            target = d.args[0].value
            break

    source_path = out / f"{stem}.c"
    binary_path = out / stem

    prompt = build_prompt(module, target)
    previous_code: str | None = None
    error_output: str | None = None

    for attempt in range(1, max_retries + 1):
        temp = 0.2 + (attempt - 1) * 0.15
        temp = min(temp, 1.0)

        log(f"\nGenerating C code (attempt {attempt}/{max_retries})...")
        if verbose:
            log(f"  Model: {model}, temperature: {temp:.2f}")

        if previous_code and error_output:
            current_prompt = build_retry_prompt(
                module, previous_code, error_output, target
            )
        else:
            current_prompt = prompt

        try:
            response = generate_code(current_prompt, model=model, temperature=temp)
        except Exception as e:
            log(f"  LLM error: {e}")
            return CompileResult(success=False, attempts=attempt, errors=[str(e)])

        c_code = extract_c_source(response)
        source_path.write_text(c_code)
        line_count = len(c_code.splitlines())
        log(f"  Wrote {source_path} ({line_count} lines)")

        log(f"Compiling {source_path}...")
        result = compile_c(
            str(source_path), str(binary_path), standard=target
        )

        if result.success:
            log(f"  Compilation successful!")
            return CompileResult(
                success=True,
                source_path=source_path,
                binary_path=binary_path,
                attempts=attempt,
            )

        error_msg = result.stderr.strip()
        log(f"  Compilation FAILED:")
        for line in error_msg.splitlines()[:10]:
            log(f"    {line}")

        previous_code = c_code
        error_output = error_msg

    return CompileResult(
        success=False,
        source_path=source_path,
        attempts=max_retries,
        errors=[error_output or "Unknown error"],
    )


def run_binary(binary_path: str | Path, log=print) -> int:
    """Execute a compiled binary and stream its output."""
    log(f"\nRunning {binary_path}...")
    log("─" * 40)
    proc = subprocess.run(
        [str(binary_path)], capture_output=True, text=True
    )
    if proc.stdout:
        log(proc.stdout.rstrip())
    if proc.stderr:
        log(proc.stderr.rstrip())
    log("─" * 40)
    if proc.returncode != 0:
        log(f"Process exited with code {proc.returncode}")
    return proc.returncode
