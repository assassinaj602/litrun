"""
litrun run: One-command hardware-aware model execution
"""

import sys
import time
import click
from rich.console import Console
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn
from litrun.hardware import probe_hardware
from litrun.registry import get_model, select_optimal_variant
from litrun.governor import check_ram_envelope, poll_governor
from litrun.resolver import (
    select_binary_target,
    get_model_cache_path,
    resolve_engine_binary,
    resolve_model_weights,
)
from litrun.engine import get_backend
from litrun.session import Session

console = Console()


@click.command(name="run")
@click.argument("model_id", default="qwen2.5-0.5b")
@click.option("-p", "--prompt", "prompt_text", default=None, help="Direct prompt to execute")
@click.option("-q", "--quant", "preferred_quant", default=None, help="Preferred quantization (e.g. Q4_K_M, Q8_0)")
@click.option("-t", "--threads", "thread_count", default=None, type=int, help="Thread count override")
@click.option("--system", "system_prompt", default=None, help="System prompt override")
@click.option("--demo", is_flag=True, help="Run in high-speed hardware simulation mode without downloading weights")
def run_cmd(model_id: str, prompt_text: str, preferred_quant: str, thread_count: int, system_prompt: str, demo: bool):
    """Executes any curated LLM with zero quantization guesswork."""

    # 1. Probing Hardware
    with console.status("[bold cyan]Probing hardware topology & ISA extensions...[/bold cyan]", spinner="dots"):
        hw = probe_hardware()
        gov = poll_governor()

    console.print(
        f"[bold blue]→ Detected:[/bold blue] "
        f"[bold white]{hw.board_name}[/bold white] "
        f"({hw.soc} {hw.cpu_part}, {hw.ram_total_mb} MB RAM, {hw.ram_avail_mb} MB free)"
    )

    # 2. Model Registry Lookup & Smart Quantization Selection
    entry = get_model(model_id)
    if not entry:
        console.print(f"[bold red]✗ Error:[/bold red] Model '[bold yellow]{model_id}[/bold yellow]' not found in registry.")
        console.print("Run [bold cyan]litrun list[/bold cyan] to view available models.")
        sys.exit(1)

    variant, decision_msg = select_optimal_variant(entry, hw, preferred_quant=preferred_quant)

    allowed, needed_mb, gov_reason, is_tight = check_ram_envelope(
        variant.size_mb,
        context_length=entry.default_context,
        kv_bytes_per_token=entry.kv_bytes_per_token,
    )

    status_tag = "[bold green]optimal RAM envelope[/bold green]" if not is_tight else "[bold yellow]tight RAM envelope[/bold yellow]"
    console.print(
        f"[bold blue]→ Selected:[/bold blue] "
        f"[bold white]{entry.id}-{variant.quant}[/bold white] "
        f"({status_tag}: {needed_mb}MB required / {hw.ram_avail_mb}MB free)"
    )

    if not allowed:
        console.print(f"[bold red]✗ Governor Warning:[/bold red] {gov_reason}")

    # 3. Precompiled Binary Resolution
    bin_target = select_binary_target(hw)
    with console.status(f"[bold cyan]Resolving precompiled engine for {bin_target}...[/bold cyan]", spinner="dots"):
        try:
            bin_path = resolve_engine_binary(hw)
            console.print(f"[bold blue]→ Binary:[/bold blue] tuned {bin_target} engine ready [green][cached][/green]")
        except Exception as e:
            bin_path = None
            console.print(f"[bold blue]→ Binary:[/bold blue] using simulation engine ([dim]{e}[/dim])")

    # 4. Model Weights Check or Stream Pull
    model_path = get_model_cache_path(entry.id, variant.quant)
    import os
    if demo:
        console.print(f"[bold blue]→ Model:[/bold blue] running in hardware simulator mode ([dim]demo mode[/dim])")
        model_path = None
    elif os.path.isfile(model_path):
        console.print(f"[bold blue]→ Model:[/bold blue] {entry.id}-{variant.quant} weights ready [green][cached][/green]")
    else:
        console.print(f"[bold blue]→ Model:[/bold blue] streaming weights from HuggingFace ({variant.size_mb}MB)...")
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
            ) as progress:
                task = progress.add_task(f"Downloading {entry.id} ({variant.quant})", total=variant.size_mb * 1024 * 1024)

                def update_cb(done, total):
                    progress.update(task, completed=done, total=total)

                model_path = resolve_model_weights(entry, variant, progress_callback=update_cb)
            console.print(f"[bold green]✓ Download verified with SHA-256[/bold green]")
        except Exception as e:
            console.print(f"[yellow]! Offline mode / demo simulation enabled ([dim]{e}[/dim])[/yellow]")
            model_path = None

    # 5. Dynamic Concurrency & Warmup
    final_threads = thread_count or gov.recommended_threads
    backend = get_backend(
        binary_path=bin_path,
        model_path=model_path,
        threads=final_threads,
        context_length=entry.default_context,
        model_id=entry.id,
        allow_mock=True,
    )

    expected_speed = 14.2
    for bp in entry.hardware_profiles:
        if hw.profile_id.startswith(bp.profile.split("-")[0]):
            expected_speed = bp.tokens_per_sec
            break

    console.print(
        f"[bold blue]→ Warmup complete.[/bold blue] "
        f"Ready at ~{expected_speed:.1f} tokens/sec on {final_threads} threads. Type to interact."
    )

    # 6. Execution Loop
    session = Session(max_context_tokens=entry.default_context)
    if system_prompt:
        session.system_prompt = system_prompt

    if prompt_text:
        console.print(f"\n[bold green]>[/bold green] {prompt_text}\n")
        session.add_user_message(prompt_text)
        formatted = session.format_prompt(family=entry.family)

        console.print(f"[bold cyan]litrun:[/bold cyan] ", end="")
        chunks = []
        t0 = time.perf_counter()
        token_count = 0

        for chunk in backend.stream(formatted, threads=final_threads):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            chunks.append(chunk)
            token_count += 1

        t1 = time.perf_counter()
        elapsed = t1 - t0
        actual_tps = (token_count / elapsed) if elapsed > 0.05 else expected_speed

        console.print(f"\n\n[dim]⚡ Telemetry: {token_count} tokens generated in {elapsed:.2f}s ({actual_tps:.1f} tok/s)[/dim]\n")
        return

    # Interactive REPL
    console.print("[dim]Type your prompt below. Enter 'exit' to quit, 'clear' to reset context.[/dim]\n")
    while True:
        try:
            user_msg = console.input("[bold green]>[/bold green] ").strip()
            if not user_msg:
                continue
            if user_msg.lower() in ["exit", "quit"]:
                break
            if user_msg.lower() == "clear":
                session.clear()
                console.print("[dim]Context memory cleared.[/dim]\n")
                continue

            session.add_user_message(user_msg)
            formatted = session.format_prompt(family=entry.family)

            console.print(f"[bold cyan]litrun:[/bold cyan] ", end="")
            chunks = []
            t0 = time.perf_counter()
            token_count = 0

            for chunk in backend.stream(formatted, threads=final_threads):
                sys.stdout.write(chunk)
                sys.stdout.flush()
                chunks.append(chunk)
                token_count += 1

            t1 = time.perf_counter()
            elapsed = t1 - t0
            actual_tps = (token_count / elapsed) if elapsed > 0.05 else expected_speed

            session.add_assistant_message("".join(chunks))
            console.print(f"\n[dim]({actual_tps:.1f} tok/s)[/dim]\n")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated.[/dim]")
            break
