"""
litrun serve: Start OpenAI-compatible HTTP REST server
"""

import click
from rich.console import Console
from litrun.server import start_server

console = Console()


@click.command(name="serve")
@click.argument("model_id", default="qwen2.5-0.5b")
@click.option("--host", default="0.0.0.0", help="Network host interface to bind")
@click.option("--port", default=8080, type=int, help="Port to listen on (default: 8080)")
def serve_cmd(model_id: str, host: str, port: int):
    """Starts an OpenAI-compatible REST server (POST /v1/chat/completions)."""
    start_server(host=host, port=port, model_id=model_id)
