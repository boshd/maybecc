"""Main pipeline: parse -> generate -> verify -> retry."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from maybecc.codegen.extractor import extract_c_source
from maybecc.codegen.llm_client import generate_code
from maybecc.codegen.prompt_builder import build_prompt, build_retry_prompt
from maybecc.parser.parser import parse_file
from maybecc.verify.runner import run_verification


@dataclass
class CompileResult:
    success: bool
    source_path: Path | None = None
    binary_path: Path | None = None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    verification_layers_that_caught_bugs: list[str] = field(default_factory=list)
    wall_time_seconds: float = 0.0


def run(
    spec_path: str,
    output_dir: str = "build",
    max_retries: int = 5,
    model: str = "claude-sonnet-4-20250514",
    verbose: bool = False,
    log=print,
) -> CompileResult:
    """Run the full pipeline: parse spec, generate C, verify, retry on failure."""
    t0 = time.time()
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
    bugs_caught_by: set[str] = set()
    attempt_log: list[dict] = []

    for attempt in range(1, max_retries + 1):
        temp = 0.2 + (attempt - 1) * 0.15
        temp = min(temp, 1.0)

        log(f"\n{'='*50}")
        log(f"Attempt {attempt}/{max_retries}")
        log(f"{'='*50}")
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
            return CompileResult(
                success=False, attempts=attempt, errors=[str(e)],
                wall_time_seconds=time.time() - t0,
            )

        c_code = extract_c_source(response)
        source_path.write_text(c_code)
        line_count = len(c_code.splitlines())
        log(f"Generated {source_path} ({line_count} lines)")

        log("Verifying...")
        status, error_detail = run_verification(
            str(source_path), module, output_dir, target=target, log=log,
        )

        attempt_log.append({
            "attempt": attempt,
            "temperature": temp,
            "status": status,
            "lines": line_count,
            "error": error_detail[:500] if error_detail else "",
        })

        if status == "pass":
            elapsed = time.time() - t0
            log(f"\nVerification PASSED on attempt {attempt} ({elapsed:.1f}s)")

            report_path = out / "verification_report.json"
            report_path.write_text(json.dumps({
                "spec_file": str(spec_path),
                "target": target,
                "status": "pass",
                "total_attempts": attempt,
                "first_pass_attempt": attempt,
                "verification_layers_that_caught_bugs": sorted(bugs_caught_by),
                "wall_time_seconds": round(elapsed, 2),
                "attempts": attempt_log,
                "generated_files": {
                    "source": str(source_path),
                    "binary": str(binary_path),
                },
            }, indent=2))
            log(f"Report: {report_path}")

            return CompileResult(
                success=True,
                source_path=source_path,
                binary_path=binary_path,
                attempts=attempt,
                verification_layers_that_caught_bugs=sorted(bugs_caught_by),
                wall_time_seconds=elapsed,
            )

        if "Compilation failed" in error_detail:
            bugs_caught_by.add("compilation")
        elif "Contract test failure" in error_detail:
            bugs_caught_by.add("contract_tests")
        elif "Runtime failure" in error_detail:
            bugs_caught_by.add("sanitizers")
        elif "Fuzz failure" in error_detail:
            bugs_caught_by.add("fuzz")

        log(f"\n  Retrying with error feedback...")
        previous_code = c_code
        error_output = error_detail

    elapsed = time.time() - t0
    report_path = out / "verification_report.json"
    report_path.write_text(json.dumps({
        "spec_file": str(spec_path),
        "target": target,
        "status": "fail",
        "total_attempts": max_retries,
        "first_pass_attempt": None,
        "verification_layers_that_caught_bugs": sorted(bugs_caught_by),
        "wall_time_seconds": round(elapsed, 2),
        "attempts": attempt_log,
    }, indent=2))

    return CompileResult(
        success=False,
        source_path=source_path,
        attempts=max_retries,
        errors=[error_output or "Unknown error"],
        verification_layers_that_caught_bugs=sorted(bugs_caught_by),
        wall_time_seconds=elapsed,
    )


def run_binary(binary_path: str | Path, log=print) -> int:
    """Execute a compiled binary and stream its output."""
    log(f"\nRunning {binary_path}...")
    log("─" * 40)
    proc = subprocess.run(
        [str(binary_path)], capture_output=True, text=True,
    )
    if proc.stdout:
        log(proc.stdout.rstrip())
    if proc.stderr:
        log(proc.stderr.rstrip())
    log("─" * 40)
    if proc.returncode != 0:
        log(f"Process exited with code {proc.returncode}")
    return proc.returncode
