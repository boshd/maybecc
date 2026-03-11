"""Generate test harnesses for contract verification."""


def generate_test_harness(module: 'Module') -> str:
    """Generate a C test harness for a module's contracts.

    Args:
        module: The parsed module specification.

    Returns:
        C source code string for the test harness.
    """
    raise NotImplementedError
