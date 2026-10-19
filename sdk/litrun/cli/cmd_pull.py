"""
litrun pull: Pre-cache model weights locally
"""

import sys
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn
from litrun.registry import get_model
from litrun.resolver import resolve_model_weights, get_model_cache_path

console = Console()


@click.command(name="pull")
@click.argument("model_id")
@click.option("-q", "--quant", "quant_name", default=None, help="Specific quantization to pull (e.g. Q4_K_M, Q8_0)")
@click.option("-f", "--force", is_flag=True, help="Force re-download even if already cached")
def pull_cmd(model_id: str, quant_name: str, force: bool):
    """Downloads and cryptographically verifies GGUF model weights into local cache."""
    entry = get_model(model_id)
    if not entry:
        console.print(f"[bold red]✗ Error:[/bold red] Model '{model_id}' not found in registry.")
        sys.exit(1)

    variant = entry.get_variant(quant_name) if quant_name else entry.get_recommended_variant()
    if not variant:
        console.print(f"[bold red]✗ Error:[/bold red] Quantization '{quant_name}' not available for {model_id}.")
        sys.exit(1)

    cached_path = get_model_cache_path(entry.id, variant.quant)
    import os
    if os.path.isfile(cached_path) and not force:
        console.print(f"[bold green]✓[/bold green] Model [bold white]{entry.id}-{variant.quant}[/bold white] is already cached at [dim]{cached_path}[/dim]")
        return

    console.print(f"[bold blue]→ Streaming model weights:[/bold blue] {entry.name} ({variant.quant}, {variant.size_mb} MB)")
    console.print(f"[dim]Source: {variant.url}[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
    ) as progress:
        task = progress.add_task(f"Pulling {entry.id}-{variant.quant}", total=variant.size_mb * 1024 * 1024)

        def update_progress(done, total):
            progress.update(task, completed=done, total=total)

        try:
            path = resolve_model_weights(
                entry,
                variant,
                force_download=force,
                progress_callback=update_progress,
            )
            console.print(f"[bold green]✓ Successfully downloaded and verified:[/bold green] {path}")
        except Exception as e:
            console.print(f"[bold red]✗ Download failed:[/bold red] {str(e)}")
            sys.exit(1)
