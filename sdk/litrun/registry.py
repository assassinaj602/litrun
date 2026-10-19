"""
litrun Metadata Registry Loader & Hardware-Aware Model Selector
"""

from __future__ import annotations
import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from litrun.hardware import HardwareProfile
from litrun.governor import check_ram_envelope


@dataclass
class ModelVariant:
    quant: str
    size_mb: int
    ram_required_mb: int
    url: str
    sha256: str
    recommended: bool = False


@dataclass
class ModelProfileBenchmark:
    profile: str
    tokens_per_sec: float
    quant: str


@dataclass
class ModelEntry:
    id: str
    name: str
    family: str
    context_length: int
    default_context: int
    kv_bytes_per_token: float
    description: str
    variants: List[ModelVariant] = field(default_factory=list)
    hardware_profiles: List[ModelProfileBenchmark] = field(default_factory=list)

    def get_variant(self, quant: str) -> Optional[ModelVariant]:
        for v in self.variants:
            if v.quant.lower() == quant.lower():
                return v
        return None

    def get_recommended_variant(self) -> ModelVariant:
        for v in self.variants:
            if v.recommended:
                return v
        return self.variants[0] if self.variants else None


def _find_registry_dir() -> str:
    """Finds the directory containing models.yaml, hardware.yaml, and binaries.yaml."""
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(pkg_dir, "registry"),
        os.path.abspath(os.path.join(pkg_dir, "..", "..", "registry")),
        "/usr/local/share/litrun/registry",
        "/etc/litrun/registry",
    ]
    for path in candidates:
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "models.yaml")):
            return path
    # Return workspace registry as fallback
    return candidates[1]


def load_models_registry() -> Dict[str, ModelEntry]:
    reg_dir = _find_registry_dir()
    models_file = os.path.join(reg_dir, "models.yaml")
    if not os.path.isfile(models_file):
        return {}

    with open(models_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    models_dict = {}
    for item in data.get("models", []):
        variants = [
            ModelVariant(
                quant=v.get("quant", ""),
                size_mb=v.get("size_mb", 0),
                ram_required_mb=v.get("ram_required_mb", 0),
                url=v.get("url", ""),
                sha256=v.get("sha256", ""),
                recommended=v.get("recommended", False),
            )
            for v in item.get("variants", [])
        ]
        benchmarks = [
            ModelProfileBenchmark(
                profile=bp.get("profile", ""),
                tokens_per_sec=float(bp.get("tokens_per_sec", 0.0)),
                quant=bp.get("quant", "Q4_K_M"),
            )
            for bp in item.get("hardware_profiles", [])
        ]
        entry = ModelEntry(
            id=item.get("id"),
            name=item.get("name", item.get("id")),
            family=item.get("family", "unknown"),
            context_length=item.get("context_length", 2048),
            default_context=item.get("default_context", 2048),
            kv_bytes_per_token=float(item.get("kv_bytes_per_token", 32.0)),
            description=item.get("description", ""),
            variants=variants,
            hardware_profiles=benchmarks,
        )
        models_dict[entry.id] = entry

    return models_dict


def load_hardware_registry() -> List[dict]:
    reg_dir = _find_registry_dir()
    hw_file = os.path.join(reg_dir, "hardware.yaml")
    if not os.path.isfile(hw_file):
        return []
    with open(hw_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("targets", [])


def load_binaries_registry() -> dict:
    reg_dir = _find_registry_dir()
    bin_file = os.path.join(reg_dir, "binaries.yaml")
    if not os.path.isfile(bin_file):
        return {}
    with open(bin_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def get_model(model_id: str) -> Optional[ModelEntry]:
    models = load_models_registry()
    if model_id in models:
        return models[model_id]
    # Check case-insensitive match
    for k, v in models.items():
        if k.lower() == model_id.lower():
            return v
    return None


def list_models() -> List[ModelEntry]:
    return list(load_models_registry().values())


def select_optimal_variant(
    model: ModelEntry,
    hw: HardwareProfile,
    preferred_quant: Optional[str] = None,
) -> tuple[ModelVariant, str]:
    """
    Evaluates hardware memory envelope and selects the optimal quantization variant.

    1. If preferred_quant is requested, verifies whether it safely fits.
    2. Otherwise, iterates available variants from highest to lowest quality (e.g. Q8_0, Q5_K_M, Q4_K_M)
       and selects the highest-accuracy quantization that comfortably fits within Available RAM * 0.85.
    3. If none fit safely, downgrades to the smallest variant and generates a safety warning.
    """
    if preferred_quant:
        var = model.get_variant(preferred_quant)
        if var:
            allowed, needed, reason, tight = check_ram_envelope(
                var.size_mb,
                context_length=model.default_context,
                kv_bytes_per_token=model.kv_bytes_per_token,
            )
            return var, reason

    # Sort variants by size descending (prefer higher quality if RAM allows)
    sorted_variants = sorted(model.variants, key=lambda v: v.size_mb, reverse=True)

    # First pass: find highest quality variant fitting in safe 85% ceiling
    for var in sorted_variants:
        allowed, needed, reason, tight = check_ram_envelope(
            var.size_mb,
            context_length=model.default_context,
            kv_bytes_per_token=model.kv_bytes_per_token,
        )
        if allowed and not tight:
            msg = f"Optimal: Selected {var.quant} ({var.size_mb}MB fits safely within {hw.ram_avail_mb}MB free RAM)"
            return var, msg

    # Second pass: if none fit in 85%, check smallest variant
    smallest_var = min(model.variants, key=lambda v: v.size_mb)
    allowed, needed, reason, tight = check_ram_envelope(
        smallest_var.size_mb,
        context_length=model.default_context,
        kv_bytes_per_token=model.kv_bytes_per_token,
    )

    if not allowed:
        msg = f"Safety Block: Even smallest quantization {smallest_var.quant} ({smallest_var.size_mb}MB) exceeds available RAM ({hw.ram_avail_mb}MB)."
    else:
        msg = f"Memory Constrained: Automatically downgraded to {smallest_var.quant} ({smallest_var.size_mb}MB) to fit into {hw.ram_avail_mb}MB free RAM."

    return smallest_var, msg

