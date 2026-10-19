"""
litrun High-Level Model Interface
Usage:
    from litrun import Model

    model = Model.load("qwen2.5-0.5b")
    for token in model.stream("Tell me about edge AI"):
        print(token, end="", flush=True)
"""

from __future__ import annotations
import sys
from typing import Generator, Optional
from litrun.hardware import HardwareProfile, probe_hardware
from litrun.governor import poll_governor, check_ram_envelope
from litrun.registry import (
    ModelEntry,
    ModelVariant,
    get_model,
    select_optimal_variant,
)
from litrun.resolver import (
    resolve_engine_binary,
    resolve_model_weights,
    get_model_cache_path,
)
from litrun.session import Session
from litrun.engine import InferenceBackend, get_backend


class Model:
    def __init__(
        self,
        entry: ModelEntry,
        variant: ModelVariant,
        hw: HardwareProfile,
        binary_path: Optional[str],
        weights_path: Optional[str],
        backend: InferenceBackend,
        threads: int,
    ):
        self.entry = entry
        self.variant = variant
        self.hw = hw
        self.binary_path = binary_path
        self.weights_path = weights_path
        self.backend = backend
        self.threads = threads
        self.session = Session(max_context_tokens=entry.default_context)

    @classmethod
    def load(
        cls,
        model_id: str,
        quant: Optional[str] = None,
        threads: Optional[int] = None,
        auto_download: bool = True,
        allow_mock: bool = True,
    ) -> "Model":
        """
        Loads an LLM model, automatically resolving hardware capabilities,
        verifying the RAM envelope, pulling prebuilt binaries and weights.
        """
        hw = probe_hardware()
        entry = get_model(model_id)

        if not entry:
            raise ValueError(
                f"Model '{model_id}' not found in registry. "
                f"Run 'litrun list' to see available models."
            )

        # Smart Quantization Selection
        variant, decision_reason = select_optimal_variant(entry, hw, preferred_quant=quant)

        # Check Governor RAM ceiling
        allowed, needed_mb, gov_reason, is_tight = check_ram_envelope(
            model_size_mb=variant.size_mb,
            context_length=entry.default_context,
            kv_bytes_per_token=entry.kv_bytes_per_token,
        )

        if not allowed and not allow_mock:
            raise MemoryError(gov_reason)

        # Dynamic Thread Allocation
        gov_status = poll_governor()
        final_threads = threads or gov_status.recommended_threads

        # Resolve binary and weights
        binary_path = None
        weights_path = None

        cached_weights = get_model_cache_path(entry.id, variant.quant)
        import os
        if os.path.isfile(cached_weights):
            weights_path = cached_weights
        elif auto_download and not allow_mock:
            try:
                weights_path = resolve_model_weights(entry, variant)
            except Exception:
                weights_path = None
        else:
            weights_path = None

        backend = get_backend(
            binary_path=binary_path,
            model_path=weights_path,
            threads=final_threads,
            context_length=entry.default_context,
            model_id=entry.id,
            allow_mock=allow_mock,
        )

        return cls(
            entry=entry,
            variant=variant,
            hw=hw,
            binary_path=binary_path,
            weights_path=weights_path,
            backend=backend,
            threads=final_threads,
        )

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Streams response tokens for a single prompt."""
        self.session.add_user_message(prompt)
        formatted_prompt = self.session.format_prompt(family=self.entry.family)

        accumulated = []
        for token in self.backend.stream(formatted_prompt, threads=self.threads, **kwargs):
            accumulated.append(token)
            yield token

        self.session.add_assistant_message("".join(accumulated))

    def generate(self, prompt: str, **kwargs) -> str:
        """Returns the complete generated string response."""
        return "".join(list(self.stream(prompt, **kwargs)))

    def chat(self) -> None:
        """Starts an interactive multi-turn terminal conversation."""
        print(f"\n--- litrun interactive session with {self.entry.name} ({self.variant.quant}) ---")
        print("Type 'exit' or Ctrl+C to quit, 'clear' to reset context.\n")

        while True:
            try:
                user_input = input("user> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    break
                if user_input.lower() == "clear":
                    self.session.clear()
                    print("[Context cleared]\n")
                    continue

                print(f"litrun> ", end="", flush=True)
                for chunk in self.stream(user_input):
                    print(chunk, end="", flush=True)
                print("\n")
            except (KeyboardInterrupt, EOFError):
                print("\n[Session ended]")
                break

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Starts an OpenAI-compatible REST server."""
        from litrun.server import start_server
        start_server(model=self, host=host, port=port)
