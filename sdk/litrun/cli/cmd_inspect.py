"""
litrun inspect: Hardware Fingerprinting & Resource Governor CLI
"""

import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from litrun.hardware import probe_hardware
from litrun.governor import poll_governor

console = Console()


@click.command(name="inspect")
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON hardware profile")
def inspect_cmd(json_output: bool):
    """Probes the underlying SBC hardware, vector extensions, and memory envelope."""
    hw = probe_hardware()
    gov = poll_governor()

    if json_output:
        combined = {
            "hardware": hw.to_dict(),
            "governor": gov.to_dict(),
        }
        click.echo(json.dumps(combined, indent=2))
        return

    # Rich Terminal Output
    title = Text("⚡ litrun Hardware Fingerprint & Resource Profile", style="bold cyan")
    console.print(Panel(title, expand=False))

    # General Hardware Table
    hw_table = Table(title="System & Processor", show_header=True, header_style="bold magenta")
    hw_table.add_column("Property", style="bold white", width=22)
    hw_table.add_column("Value", style="green")

    hw_table.add_row("Canonical Profile ID", f"[bold yellow]{hw.profile_id}[/bold yellow]")
    hw_table.add_row("Board Model", hw.board_name)
    hw_table.add_row("SoC Model", hw.soc)
    hw_table.add_row("CPU Microarchitecture", hw.cpu_part)
    hw_table.add_row("Architecture / ABI", hw.arch)
    hw_table.add_row("Logical CPU Cores", str(hw.cores))

    console.print(hw_table)

    # Memory & Thermals Table
    mem_table = Table(title="Memory Envelope & Thermals", show_header=True, header_style="bold magenta")
    mem_table.add_column("Metric", style="bold white", width=22)
    mem_table.add_column("Value", style="cyan")

    mem_table.add_row("Physical RAM Total", f"{hw.ram_total_mb} MB")
    mem_table.add_row("Physical RAM Available", f"[bold green]{hw.ram_avail_mb} MB[/bold green]")
    mem_table.add_row("Swap Total / Free", f"{hw.swap_total_mb} MB / {hw.swap_free_mb} MB")

    if hw.temp_c > 0:
        temp_color = "green" if hw.temp_c < 75 else ("yellow" if hw.temp_c < 80 else "bold red")
        mem_table.add_row("Thermal Zone 0", f"[{temp_color}]{hw.temp_c}°C ({gov.thermal_state})[/{temp_color}]")
    else:
        mem_table.add_row("Thermal Zone 0", "[dim]Unavailable[/dim]")

    mem_table.add_row("Recommended Threads", f"{gov.recommended_threads} threads")

    console.print(mem_table)

    # Vector Extensions Table
    vec_table = Table(title="Hardware ISA Vector Acceleration", show_header=True, header_style="bold magenta")
    vec_table.add_column("Extension", style="bold white", width=22)
    vec_table.add_column("Status", width=12)
    vec_table.add_column("Impact on Small LLMs", style="dim")

    def fmt_flag(val: bool, note: str):
        status = "[bold green]YES[/bold green]" if val else "[red]NO[/red]"
        return status, note

    if hw.arch in ["aarch64", "arm64", "armv7l"]:
        s, note = fmt_flag(hw.has_neon, "Baseline 128-bit SIMD vector engine")
        vec_table.add_row("ARM NEON (ASIMD)", s, note)

        s, note = fmt_flag(hw.has_dotprod, "sdot/udot INT8 acceleration (Pi 5 / RK3588)")
        vec_table.add_row("Dot Product (ASIMDDP)", s, note)

        s, note = fmt_flag(hw.has_fp16, "Native half-precision floating point ops")
        vec_table.add_row("FP16 (FPHP)", s, note)

        s, note = fmt_flag(hw.has_i8mm, "Int8 matrix multiplication extensions")
        vec_table.add_row("I8MM", s, note)

        s, note = fmt_flag(hw.has_sve, "Scalable Vector Extension")
        vec_table.add_row("ARM SVE", s, note)
    else:
        s, note = fmt_flag(hw.has_avx, "Advanced Vector Extensions 256-bit")
        vec_table.add_row("x86 AVX", s, note)

        s, note = fmt_flag(hw.has_avx2, "Fused Integer Vector ops (crucial for quant speed)")
        vec_table.add_row("x86 AVX2", s, note)

        s, note = fmt_flag(hw.has_fma, "Fused Multiply-Add")
        vec_table.add_row("x86 FMA", s, note)

        s, note = fmt_flag(hw.has_avx512, "512-bit vector registers")
        vec_table.add_row("x86 AVX-512", s, note)

    if hw.has_rknn:
        vec_table.add_row("Rockchip RKNN NPU", "[bold green]DETECTED[/bold green]", "/dev/rknpu hardware node accessible")
    if hw.has_nvdla:
        vec_table.add_row("NVIDIA NVDLA", "[bold green]DETECTED[/bold green]", "Jetson deep learning accelerator accessible")

    console.print(vec_table)

