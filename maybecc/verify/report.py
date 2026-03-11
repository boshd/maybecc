"""Verification report schema.

Every attempt is logged with full detail across all verification stages.
This is the primary empirical artifact for demonstrating the NTM thesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StageResult:
    status: str  # "pass", "fail", "not_reached"
    output: str = ""


@dataclass
class CompilationResult:
    status: str
    compiler: str = "clang"
    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class SanitizerResults:
    status: str
    asan: StageResult = field(default_factory=lambda: StageResult("not_reached"))
    ubsan: StageResult = field(default_factory=lambda: StageResult("not_reached"))


@dataclass
class ContractTestResults:
    status: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass
class FuzzResults:
    status: str
    iterations_requested: int = 0
    iterations_completed: int = 0
    coverage_pct: Optional[float] = None
    crashes: list[str] = field(default_factory=list)


@dataclass
class Attempt:
    attempt: int
    model: str
    temperature: float
    timestamp_utc: str
    compilation: CompilationResult
    sanitizers: SanitizerResults
    contract_tests: ContractTestResults
    fuzz: FuzzResults


@dataclass
class VerificationReport:
    spec_file: str
    target: str
    status: str  # "pass" or "fail"
    attempts: list[Attempt] = field(default_factory=list)
    total_attempts: int = 0
    first_pass_attempt: Optional[int] = None
    verification_layers_that_caught_bugs: list[str] = field(default_factory=list)
    wall_time_seconds: float = 0.0
    generated_files: dict[str, str] = field(default_factory=dict)
