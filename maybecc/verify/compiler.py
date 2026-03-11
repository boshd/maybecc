"""Compile C source files using the system C compiler."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class CompilationResult:
    success: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def find_compiler() -> str:
    """Find an available C compiler, preferring clang."""
    for name in ("clang", "cc", "gcc"):
        if shutil.which(name):
            return name
    raise RuntimeError("No C compiler found. Install clang or gcc.")


def compile_c(
    source_path: str,
    output_path: str,
    standard: str = "c99",
    extra_flags: list[str] | None = None,
) -> CompilationResult:
    """Compile a C source file to an executable."""
    compiler = find_compiler()
    cmd = [
        compiler,
        "-Wall",
        "-Werror",
        f"-std={standard}",
        "-o",
        output_path,
        source_path,
    ]
    if extra_flags:
        cmd.extend(extra_flags)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    return CompilationResult(
        success=proc.returncode == 0,
        command=cmd,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )
