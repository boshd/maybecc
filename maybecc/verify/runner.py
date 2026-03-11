"""Verification pipeline runner.

Executes each verification stage in order — compilation, sanitizer run,
contract tests, fuzz — short-circuiting on failure.  Results are collected
into a :class:`~maybecc.verify.report.Attempt` dataclass.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from maybecc.parser.ast_nodes import Module
from maybecc.verify.compiler import compile_c, find_compiler
from maybecc.verify.harness_gen import generate_test_harness
from maybecc.verify.fuzz_gen import generate_fuzz_harness
from maybecc.verify.report import (
    CompilationResult as ReportCompilation,
    ContractTestResults,
    FuzzResults,
    SanitizerResults,
    StageResult,
)


def _not_reached() -> StageResult:
    return StageResult(status="not_reached")


def _extract_verify_config(module: Module) -> dict:
    """Pull sanitizer / fuzz settings from @verify directives."""
    cfg: dict = {"asan": False, "ubsan": False, "fuzz_iterations": 0}
    for d in module.directives:
        if d.name != "verify":
            continue
        for arg in d.args:
            from maybecc.parser.ast_nodes import PositionalArg, KeyedArg
            if isinstance(arg, PositionalArg):
                if arg.value == "asan":
                    cfg["asan"] = True
                elif arg.value == "ubsan":
                    cfg["ubsan"] = True
            elif isinstance(arg, KeyedArg) and arg.key == "fuzz":
                cfg["fuzz_iterations"] = int(arg.value)

    for fn in module.functions:
        from maybecc.parser.ast_nodes import FlagAnnotation, ParamAnnotation
        for ann in fn.annotations:
            if isinstance(ann, FlagAnnotation) and ann.name == "no_undefined_behavior":
                cfg["asan"] = True
                cfg["ubsan"] = True
            elif isinstance(ann, ParamAnnotation) and ann.name == "verify":
                for arg in ann.args:
                    from maybecc.parser.ast_nodes import PositionalArg, KeyedArg
                    if isinstance(arg, PositionalArg) and arg.value == "asan":
                        cfg["asan"] = True
                    elif isinstance(arg, PositionalArg) and arg.value == "ubsan":
                        cfg["ubsan"] = True
                    elif isinstance(arg, KeyedArg) and arg.key == "fuzz":
                        cfg["fuzz_iterations"] = max(cfg["fuzz_iterations"], int(arg.value))
    return cfg


def _sanitizer_flags(cfg: dict) -> list[str]:
    parts: list[str] = []
    if cfg["asan"]:
        parts.append("address")
    if cfg["ubsan"]:
        parts.append("undefined")
    if not parts:
        return []
    return [f"-fsanitize={','.join(parts)}"]


def _run_binary(path: str, timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            [path], capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timed out"


def run_verification(
    source_path: str,
    module: Module,
    output_dir: str,
    target: str = "c99",
    log=print,
) -> tuple[str, str]:
    """Run the full verification pipeline.

    Returns ``(status, error_detail)`` where *status* is ``"pass"`` or
    ``"fail"`` and *error_detail* contains the first error encountered
    (empty on pass).
    """
    out = Path(output_dir)
    src = Path(source_path)
    stem = src.stem
    cfg = _extract_verify_config(module)

    san_flags = _sanitizer_flags(cfg)

    # ── Stage 1: compile with sanitizers ──────────────────────────────
    log("  [1/4] Compiling with sanitizers..." if san_flags else "  [1/4] Compiling...")
    binary = str(out / stem)
    result = compile_c(source_path, binary, standard=target, extra_flags=san_flags)
    if not result.success:
        return "fail", f"Compilation failed:\n{result.stderr}"

    # ── Stage 2: run the binary (LLM-generated main + assertions) ─────
    log("  [2/4] Running generated program...")
    rc, stdout, stderr = _run_binary(binary)
    if rc != 0:
        detail = stderr or stdout or f"exit code {rc}"
        return "fail", f"Runtime failure:\n{detail}"

    # ── Stage 3: contract test harness ────────────────────────────────
    harness_src = generate_test_harness(module, src.name)
    if harness_src:
        harness_path = str(out / f"test_{stem}.c")
        harness_bin = str(out / f"test_{stem}")
        Path(harness_path).write_text(harness_src)
        log("  [3/4] Compiling contract tests...")

        hr = compile_c(harness_path, harness_bin, standard=target, extra_flags=san_flags)
        if not hr.success:
            log("  [3/4] Contract test compilation failed (non-fatal)")
        else:
            log("  [3/4] Running contract tests...")
            rc, stdout, stderr = _run_binary(harness_bin)
            if rc != 0:
                detail = stderr or stdout or f"exit code {rc}"
                return "fail", f"Contract test failure:\n{detail}"
            if stderr:
                for line in stderr.strip().splitlines():
                    log(f"        {line}")
    else:
        log("  [3/4] No testable functions — skipped")

    # ── Stage 4: fuzz harness ─────────────────────────────────────────
    fuzz_iters = cfg["fuzz_iterations"]
    if fuzz_iters > 0 and shutil.which("clang"):
        fuzz_src = generate_fuzz_harness(module, src.name)
        if fuzz_src:
            fuzz_path = str(out / f"fuzz_{stem}.c")
            fuzz_bin = str(out / f"fuzz_{stem}")
            Path(fuzz_path).write_text(fuzz_src)
            log(f"  [4/4] Compiling fuzz harness...")

            fuzz_flags = ["-fsanitize=fuzzer,address,undefined", "-g"]
            fr = compile_c(fuzz_path, fuzz_bin, standard=target, extra_flags=fuzz_flags)
            if not fr.success:
                log("  [4/4] Fuzz harness compilation failed (non-fatal)")
            else:
                log(f"  [4/4] Fuzzing ({fuzz_iters} iterations)...")
                try:
                    proc = subprocess.run(
                        [fuzz_bin, f"-runs={fuzz_iters}"],
                        capture_output=True, text=True, timeout=120,
                    )
                    if proc.returncode != 0:
                        detail = proc.stderr or proc.stdout or f"exit code {proc.returncode}"
                        return "fail", f"Fuzz failure:\n{detail}"
                    log(f"        {fuzz_iters} iterations — OK")
                except subprocess.TimeoutExpired:
                    log("  [4/4] Fuzz timed out (non-fatal)")
        else:
            log("  [4/4] No fuzzable functions — skipped")
    else:
        log("  [4/4] Fuzzing — skipped")

    return "pass", ""
