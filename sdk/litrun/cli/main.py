"""
litrun CLI Entrypoint
"""

import click
from rich.console import Console
from litrun import __version__
from litrun.cli.cmd_inspect import inspect_cmd
from litrun.cli.cmd_run import run_cmd
from litrun.cli.cmd_pull import pull_cmd
from litrun.cli.cmd_list import list_cmd
from litrun.cli.cmd_serve import serve_cmd
from litrun.cli.cmd_bench import bench_cmd

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="litrun")
def cli():
    """⚡ litrun: Universal Lightweight Embedded Linux AI Runtime"""
    pass


cli.add_command(inspect_cmd, name="inspect")
cli.add_command(run_cmd, name="run")
cli.add_command(pull_cmd, name="pull")
cli.add_command(list_cmd, name="list")
cli.add_command(serve_cmd, name="serve")
cli.add_command(bench_cmd, name="benchmark")

if __name__ == "__main__":
    cli()
