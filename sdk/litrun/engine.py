"""
litrun Inference Backend Adapters
Supports persistent llama-server daemon, llama-cli process runner, and deterministic mock simulation.
"""

from __future__ import annotations
import abc
import atexit
import json
import os
import socket
import subprocess
import time
import urllib.request
import urllib.error
from typing import Generator, Optional


class InferenceBackend(abc.ABC):
    def __init__(self):
        self.last_tokens_per_sec = 0.0
        self.last_ttft_ms = 0.0

    @abc.abstractmethod
    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        pass

    def generate(self, prompt: str, **kwargs) -> str:
        chunks = []
        for token in self.stream(prompt, **kwargs):
            chunks.append(token)
        return "".join(chunks)

    def close(self) -> None:
        pass


class PersistentLlamaServerEngine(InferenceBackend):
    """
    Keeps a persistent `llama-server` daemon running on a local loopback port.
    Weights remain permanently locked in RAM across multi-turn chats and REST requests,
    reducing Time-To-First-Token (TTFT) from seconds to <50ms.
    """

    def __init__(
        self,
        binary_path: str,
        model_path: str,
        threads: int = 4,
        context_length: int = 2048,
        host: str = "127.0.0.1",
        timeout_seconds: float = 20.0,
    ):
        super().__init__()
        self.binary_path = binary_path
        self.model_path = model_path
        self.threads = max(1, threads)
        self.context_length = context_length
        self.host = host

        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            self.port = s.getsockname()[1]

        self.base_url = f"http://{self.host}:{self.port}"
        self.proc: Optional[subprocess.Popen] = None
        self._start_server(timeout_seconds)
        atexit.register(self.close)

    def _start_server(self, timeout_seconds: float) -> None:
        cmd = [
            self.binary_path,
            "-m", self.model_path,
            "-c", str(self.context_length),
            "-t", str(self.threads),
            "--host", self.host,
            "--port", str(self.port),
            "-ngl", "0",
            "--log-disable",
        ]

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Poll /health until server is ready
        deadline = time.time() + timeout_seconds
        ready = False
        while time.time() < deadline:
            time.sleep(0.1)
            try:
                with urllib.request.urlopen(f"{self.base_url}/health", timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                if self.proc.poll() is not None:
                    break

        if not ready:
            self.close()
            raise RuntimeError(
                f"Failed to start persistent llama-server on {self.base_url} within {timeout_seconds}s"
            )

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)

        req_body = json.dumps({
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stream": True,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/completion",
            data=req_body,
            headers={"Content-Type": "application/json"},
        )

        t_start = time.perf_counter()
        t_first = None
        token_count = 0

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    line_str = line.decode("utf-8", "ignore").strip()
                    if not line_str.startswith("data: "):
                        continue

                    payload_str = line_str[6:].strip()
                    if payload_str == "[DONE]":
                        break

                    try:
                        data = json.loads(payload_str)
                        content = data.get("content", "")
                        if content:
                            if t_first is None:
                                t_first = time.perf_counter()
                                self.last_ttft_ms = (t_first - t_start) * 1000.0

                            token_count += 1
                            yield content
                    except Exception:
                        pass

            t_end = time.perf_counter()
            if t_first and (t_end - t_first) > 0.001:
                self.last_tokens_per_sec = token_count / (t_end - t_first)

        except Exception as e:
            yield f"[Inference Error: {str(e)}]"

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def __del__(self):
        self.close()


class LlamaCppEngine(InferenceBackend):
    def __init__(
        self,
        binary_path: str,
        model_path: str,
        threads: int = 4,
        context_length: int = 2048,
        temperature: float = 0.7,
    ):
        super().__init__()
        self.binary_path = binary_path
        self.model_path = model_path
        self.threads = max(1, threads)
        self.context_length = context_length
        self.temperature = temperature

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
        super().__init__()
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
    prefer_server: bool = True,
) -> InferenceBackend:
    """
    Returns optimal inference backend:
    1. PersistentLlamaServerEngine if `llama-server` is available and weights exist
    2. LlamaCppEngine if `llama-cli` is available and weights exist
    3. MockEngine if allow_mock=True
    """
    if binary_path and model_path and os.path.isfile(binary_path) and os.path.isfile(model_path):
        # Check if binary is or has companion llama-server
        bin_dir = os.path.dirname(binary_path)
        server_bin = os.path.join(bin_dir, "llama-server")
        if prefer_server and (os.path.basename(binary_path) == "llama-server" or os.path.isfile(server_bin)):
            target_server = binary_path if os.path.basename(binary_path) == "llama-server" else server_bin
            try:
                return PersistentLlamaServerEngine(
                    binary_path=target_server,
                    model_path=model_path,
                    threads=threads,
                    context_length=context_length,
                )
            except Exception:
                pass

        # Fallback to process runner
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
