"""Generate fuzz harnesses for verification."""


def generate_fuzz_harness(module: 'Module') -> str:
    """Generate a C fuzz harness for a module.

    Args:
        module: The parsed module specification.

    Returns:
        C source code string for the fuzz harness.
    """
    raise NotImplementedError
