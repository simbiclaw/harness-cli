"""CLI entry point.

This file is the only thing Typer needs to register the `argus` command.
Subcommands are added by feature ExecPlans. This stub exists so that the
package is importable and the entry point resolves at install time.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="argus",
    help="Replace this with the real one-line description.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the package version."""
    from argus import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
