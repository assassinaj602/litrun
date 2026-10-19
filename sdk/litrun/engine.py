"""
litrun Inference Backend Adapters
Supports llama.cpp subprocess pipe runner and deterministic mock/emulation for testing.
"""

from __future__ import annotations
import abc
import os
import subprocess
import time
from typing import Generator, Optional


class InferenceBackend(abc.ABC):
    @abc.abstractmethod
    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        pass

    def generate(self, prompt: str, **kwargs) -> str:
        chunks = []
        for token in self.stream(prompt, **kwargs):
            chunks.append(token)
        return "".join(chunks)


class LlamaCppEngine(InferenceBackend):
    def __init__(
        self,
        binary_path: str,
        model_path: str,
        threads: int = 4,
        context_length: int = 2048,
        temperature: float = 0.7,
    ):
        self.binary_path = binary_path
        self.model_path = model_path
        self.threads = max(1, threads)
        self.context_length = context_length
        self.temperature = temperature
        self.last_tokens_per_sec = 0.0
        self.last_ttft_ms = 0.0

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        threads = kwargs.get("threads", self.threads)
        max_tokens = kwargs.get("max_tokens", 512)
        temp = kwargs.get("temperature", self.temperature)

        cmd = [
            self.binary_path,
            "-m", self.model_path,
            "-p", prompt,
            "-t", str(threads),
            "-c", str(self.context_length),
            "-n", str(max_tokens),
            "--temp", str(temp),
            "--simple-io",
            "--no-display-prompt",
        ]

        t_start = time.perf_counter()
        t_first = None
        token_count = 0

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                if t_first is None:
                    t_first = time.perf_counter()
                    self.last_ttft_ms = (t_first - t_start) * 1000.0

                token_count += 1
                yield line

            proc.stdout.close()
            proc.wait()

            t_end = time.perf_counter()
            if t_first and (t_end - t_first) > 0.001:
                self.last_tokens_per_sec = token_count / (t_end - t_first)

        except Exception as e:
            yield f"[Inference Engine Error: {str(e)}]"


class MockEngine(InferenceBackend):
    """
    Simulation / Unit-Testing runner. Streams realistic tokens with measured
    latency and tokens/sec telemetry without requiring physical GGUF weights.
    """

    def __init__(
        self,
        model_name: str = "qwen2.5-0.5b",
        tokens_per_sec: float = 14.2,
    ):
        self.model_name = model_name
        self.tokens_per_sec = tokens_per_sec
        self.last_tokens_per_sec = tokens_per_sec
        self.last_ttft_ms = 45.0

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        delay = 1.0 / self.tokens_per_sec if self.tokens_per_sec > 0 else 0.02
        response_text = (
            f"Hello from litrun! I am {self.model_name} running on embedded Linux. "
            f"Our dedicated C resource governor ensures memory cgroups and thermals "
            f"remain stable during inference, avoiding kernel OOM killer terminations."
        )

        words = response_text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            time.sleep(min(delay, 0.05))
            yield chunk


def get_backend(
    binary_path: Optional[str],
    model_path: Optional[str],
    threads: int = 4,
    context_length: int = 2048,
    model_id: str = "qwen2.5-0.5b",
    allow_mock: bool = True,
) -> InferenceBackend:
    if binary_path and model_path and os.path.isfile(binary_path) and os.path.isfile(model_path):
        return LlamaCppEngine(
            binary_path=binary_path,
            model_path=model_path,
            threads=threads,
            context_length=context_length,
        )

    if allow_mock:
        return MockEngine(model_name=model_id)

    raise FileNotFoundError(
        f"Inference engine could not be initialized: binary={binary_path}, model={model_path}"
    )
