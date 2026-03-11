"""CLI entry point for maybecc."""

from __future__ import annotations

import sys

import click


@click.group()
def main():
    """maybecc — a non-deterministic compiler."""
    pass


@main.command()
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("-o", "--output", default="build/", help="Output directory")
@click.option("--max-retries", default=5, help="Max LLM generation attempts")
@click.option("--model", default="claude-sonnet-4-20250514", help="Anthropic model")
@click.option("--run", "run_after", is_flag=True, help="Run the binary after compilation")
@click.option("--verbose", is_flag=True, help="Verbose output")
def compile(spec_file, output, max_retries, model, run_after, verbose):
    """Compile a .mcc spec file to verified C code."""
    from maybecc.orchestrator import run, run_binary

    result = run(
        spec_path=spec_file,
        output_dir=output,
        max_retries=max_retries,
        model=model,
        verbose=verbose,
        log=click.echo,
    )

    if not result.success:
        click.echo(
            f"\nFailed after {result.attempts} attempt(s).", err=True
        )
        for err in result.errors:
            for line in err.splitlines()[:5]:
                click.echo(f"  {line}", err=True)
        sys.exit(1)

    if result.verification_layers_that_caught_bugs:
        layers = ", ".join(result.verification_layers_that_caught_bugs)
        click.echo(f"Verification layers that caught bugs: {layers}")

    click.echo(
        f"Done in {result.attempts} attempt(s), "
        f"{result.wall_time_seconds:.1f}s: {result.binary_path}"
    )

    if run_after and result.binary_path:
        rc = run_binary(result.binary_path, log=click.echo)
        sys.exit(rc)


@main.command()
@click.argument("spec_file", type=click.Path(exists=True))
def parse(spec_file):
    """Parse a .mcc spec file and print its AST summary."""
    from maybecc.parser.parser import parse_file

    module = parse_file(spec_file)
    click.echo(f"Directives: {len(module.directives)}")
    for d in module.directives:
        click.echo(f"  @{d.name}({', '.join(str(a) for a in d.args)})")

    if module.enums:
        click.echo(f"Enums: {len(module.enums)}")
        for e in module.enums:
            click.echo(f"  {e.name}: {', '.join(e.variants)}")

    if module.structs:
        click.echo(f"Structs: {len(module.structs)}")
        for s in module.structs:
            click.echo(f"  {s.name}: {len(s.fields)} fields")

    click.echo(f"Functions: {len(module.functions)}")
    for fn in module.functions:
        ann_types = [type(a).__name__ for a in fn.annotations]
        click.echo(
            f"  {fn.name}: {len(fn.params)} params, {', '.join(ann_types)}"
        )
