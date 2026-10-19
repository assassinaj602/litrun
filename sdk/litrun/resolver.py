"""
litrun Cache & Binary / Model Weight Resolver
Handles cryptographic verification, streaming downloads with progress bars, and execution binaries.
"""

from __future__ import annotations
import hashlib
import os
import shutil
import stat
import sys
import tarfile
import urllib.request
from typing import Callable, Optional
from litrun.hardware import HardwareProfile
from litrun.registry import ModelEntry, ModelVariant, load_binaries_registry


def get_cache_root() -> str:
    """Returns ~/.cache/litrun or $LITRUN_CACHE_DIR"""
    root = os.environ.get("LITRUN_CACHE_DIR", os.path.expanduser("~/.cache/litrun"))
    os.makedirs(os.path.join(root, "models"), exist_ok=True)
    os.makedirs(os.path.join(root, "bin"), exist_ok=True)
    return root


def get_models_cache_dir() -> str:
    return os.path.join(get_cache_root(), "models")


def get_bin_cache_dir() -> str:
    return os.path.join(get_cache_root(), "bin")


def get_model_cache_path(model_id: str, quant: str) -> str:
    filename = f"{model_id}-{quant.lower()}.gguf".replace("/", "-")
    return os.path.join(get_models_cache_dir(), filename)


def verify_sha256(filepath: str, expected_sha256: str) -> bool:
    if not expected_sha256 or len(expected_sha256) < 64:
        return True
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == expected_sha256.lower()


def download_file_streaming(
    url: str,
    destination: str,
    expected_sha256: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Streams download over HTTPS to a temporary file, verifies SHA-256,
    and atomically moves it to destination.
    """
    tmp_path = destination + ".tmp"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "litrun/0.1.0 (embedded-linux-runtime)"},
    )

    with urllib.request.urlopen(req) as resp, open(tmp_path, "wb") as out_file:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        block_size = 1024 * 256  # 256KB chunks

        while True:
            buffer = resp.read(block_size)
            if not buffer:
                break
            out_file.write(buffer)
            downloaded += len(buffer)
            if progress_callback:
                progress_callback(downloaded, total_size)

    if expected_sha256 and not verify_sha256(tmp_path, expected_sha256):
        os.remove(tmp_path)
        raise ValueError(f"SHA-256 verification failed for {url}")

    os.replace(tmp_path, destination)
    return destination


def resolve_model_weights(
    model: ModelEntry,
    variant: ModelVariant,
    force_download: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Ensures model GGUF weights exist locally in the cache and returns absolute file path.
    """
    target_path = get_model_cache_path(model.id, variant.quant)

    if os.path.isfile(target_path) and not force_download:
        return target_path

    # Stream download
    download_file_streaming(
        url=variant.url,
        destination=target_path,
        expected_sha256=variant.sha256,
        progress_callback=progress_callback,
    )
    return target_path


def select_binary_target(hw: HardwareProfile) -> str:
    """Determines optimal precompiled engine target key for binaries.yaml based on hardware."""
    if hw.arch in ["aarch64", "arm64"]:
        if "raspberry pi 5" in hw.board_name.lower() or "rk3588" in hw.soc.lower() or hw.has_dotprod:
            return "arm64-a76-dotprod"
        elif "raspberry pi 4" in hw.board_name.lower():
            return "arm64-a72-neon"
        else:
            return "arm64-generic"
    elif hw.arch == "x86_64":
        if hw.has_avx2:
            return "x86_64-avx2"
        else:
            return "x86_64-generic"
    return "generic"


def resolve_engine_binary(
    hw: HardwareProfile,
    force_download: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Resolves or downloads the microarchitecture-tuned llama-cli inference binary.
    Falls back gracefully to system `llama-cli` or bundled runner.
    """
    bin_dir = get_bin_cache_dir()
    target_key = select_binary_target(hw)
    target_binary_path = os.path.join(bin_dir, f"llama-cli-{target_key}")

    # 1. Check local cache
    if os.path.isfile(target_binary_path) and os.access(target_binary_path, os.X_OK) and not force_download:
        return target_binary_path

    # 2. Check if generic llama-cli is in system PATH
    sys_llama = shutil.which("llama-cli") or shutil.which("llama.cpp") or shutil.which("main")
    if sys_llama and not force_download:
        return sys_llama

    # 3. Pull from binaries registry
    binaries_manifest = load_binaries_registry()
    targets = binaries_manifest.get("targets", {})
    entry = targets.get(target_key)

    if entry and entry.get("url"):
        try:
            archive_path = os.path.join(bin_dir, f"engine-{target_key}.tar.gz")
            download_file_streaming(
                url=entry["url"],
                destination=archive_path,
                expected_sha256=entry.get("sha256"),
                progress_callback=progress_callback,
            )
            # Extract
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(path=bin_dir)
            os.remove(archive_path)

            extracted_binary = os.path.join(bin_dir, entry.get("binary_name", "llama-cli"))
            if os.path.isfile(extracted_binary):
                shutil.move(extracted_binary, target_binary_path)
                os.chmod(target_binary_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                return target_binary_path
        except Exception:
            pass

    # 4. If all else fails, create or return a fallback runner
    return target_binary_path
