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
    prefer_server: bool = True,
    force_download: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Resolves or downloads the microarchitecture-tuned llama.cpp binary.
    Prioritizes persistent `llama-server` for sub-100ms TTFT, with fallback to `llama-cli`.
    """
    bin_dir = get_bin_cache_dir()
    target_key = select_binary_target(hw)

    server_candidates = [
        os.path.join(bin_dir, "llama-server"),
        os.path.join(bin_dir, f"llama-server-{target_key}"),
        shutil.which("llama-server"),
    ]
    cli_candidates = [
        os.path.join(bin_dir, "llama-cli"),
        os.path.join(bin_dir, f"llama-cli-{target_key}"),
        shutil.which("llama-cli"),
        shutil.which("llama.cpp"),
        shutil.which("main"),
    ]

    # 1. Check existing binaries if not force_download
    if not force_download:
        if prefer_server:
            for cand in server_candidates:
                if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
                    return cand
        for cand in cli_candidates:
            if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand

    # 2. Pull from binaries registry if missing
    binaries_manifest = load_binaries_registry()
    targets = binaries_manifest.get("targets", {})

    candidate_keys = [target_key]
    if hw.arch in ["aarch64", "arm64"] and target_key != "arm64-generic":
        candidate_keys.append("arm64-generic")
    elif hw.arch == "x86_64" and target_key != "x86_64-generic":
        candidate_keys.append("x86_64-generic")

    for key in candidate_keys:
        entry = targets.get(key)
        if entry and entry.get("url"):
            try:
                archive_path = os.path.join(bin_dir, f"engine-{key}.tar.gz")
                download_file_streaming(
                    url=entry["url"],
                    destination=archive_path,
                    expected_sha256=entry.get("sha256"),
                    progress_callback=progress_callback,
                )
                # Extract tarball
                with tarfile.open(archive_path, "r:*") as tar:
                    tar.extractall(path=bin_dir)
                os.remove(archive_path)

                # Discover and chmod binaries across top-level or subdirectories
                for root, _, files in os.walk(bin_dir):
                    for f in files:
                        if f in ["llama-server", "llama-cli"]:
                            full_f = os.path.join(root, f)
                            target_dst = os.path.join(bin_dir, f)
                            if full_f != target_dst:
                                shutil.copy2(full_f, target_dst)
                            os.chmod(target_dst, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

                if prefer_server and os.path.isfile(os.path.join(bin_dir, "llama-server")):
                    return os.path.join(bin_dir, "llama-server")
                if os.path.isfile(os.path.join(bin_dir, "llama-cli")):
                    return os.path.join(bin_dir, "llama-cli")
            except Exception:
                continue

    # 3. Fallback candidates check
    for cand in (server_candidates if prefer_server else cli_candidates) + cli_candidates:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand

    return os.path.join(bin_dir, "llama-server" if prefer_server else "llama-cli")


