"""Run verification pipeline (compile, sanitizers, contract tests, fuzz)."""


def run_verification(source_path: str, module: 'Module') -> 'VerificationReport':
    """Run the full verification pipeline on generated C code.

    Args:
        source_path: Path to the C source file to verify.
        module: The parsed module specification.

    Returns:
        Verification report with all stage results.
    """
    raise NotImplementedError
