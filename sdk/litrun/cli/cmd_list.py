"""
litrun list: Catalog of models and local cache status
"""

import os
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from litrun.registry import list_models
from litrun.resolver import get_models_cache_dir, get_bin_cache_dir

console = Console()


@click.command(name="list")
def list_cmd():
    """Lists curated edge LLMs, available quantizations, and local cache status."""
    models = list_models()
    cache_dir = get_models_cache_dir()

    title = Text("⚡ litrun Model & Binary Registry", style="bold cyan")
    console.print(Panel(title, expand=False))

    table = Table(title="Curated Embedded AI Models", show_header=True, header_style="bold magenta")
    table.add_column("Model ID", style="bold yellow", no_wrap=True)
    table.add_column("Model Name", style="bold white")
    table.add_column("Context", justify="right")
    table.add_column("Quant", style="cyan")
    table.add_column("Weight", justify="right")
    table.add_column("RAM Min", justify="right")
    table.add_column("Status")

    for m in models:
        rec = m.get_recommended_variant()
        target_path = os.path.join(cache_dir, f"{m.id}-{rec.quant.lower()}.gguf".replace("/", "-"))
        is_cached = os.path.isfile(target_path)
        status_str = "[bold green]CACHED[/bold green]" if is_cached else "[dim]Available[/dim]"

        table.add_row(
            m.id,
            m.name,
            f"{m.default_context}",
            rec.quant,
            f"{rec.size_mb} MB",
            f"{rec.ram_required_mb} MB",
            status_str,
        )

    console.print(table)

    # Cached Binaries
    bin_dir = get_bin_cache_dir()
    bin_files = os.listdir(bin_dir) if os.path.isdir(bin_dir) else []

    if bin_files:
        bin_table = Table(title="Cached Inference Engine Binaries", show_header=True, header_style="bold magenta")
        bin_table.add_column("Engine Target", style="bold green")
        bin_table.add_column("Path", style="dim")

        for bf in bin_files:
            p = os.path.join(bin_dir, bf)
            bin_table.add_row(bf, p)

        console.print(bin_table)
    else:
        console.print("[dim]No precompiled inference engine binaries cached yet. (They will auto-pull on first 'litrun run').[/dim]\n")
