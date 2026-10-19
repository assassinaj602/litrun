from litrun.registry import (
    load_models_registry,
    load_hardware_registry,
    load_binaries_registry,
    get_model,
    list_models,
    select_optimal_variant,
)
from litrun.hardware import probe_hardware


def test_load_models_registry():
    models = load_models_registry()
    assert len(models) >= 4
    assert "qwen2.5-0.5b" in models
    assert "llama-3.2-1b" in models

    qwen = models["qwen2.5-0.5b"]
    assert qwen.name == "Qwen 2.5 0.5B Instruct"
    assert qwen.family == "qwen"
    assert len(qwen.variants) >= 2


def test_get_model():
    m = get_model("qwen2.5-0.5b")
    assert m is not None
    assert m.id == "qwen2.5-0.5b"

    rec = m.get_recommended_variant()
    assert rec is not None
    assert rec.quant == "Q4_K_M"


def test_select_optimal_variant():
    hw = probe_hardware()
    entry = get_model("qwen2.5-0.5b")
    variant, msg = select_optimal_variant(entry, hw)
    assert variant is not None
    assert variant.quant in ["Q4_K_M", "Q5_K_M", "Q8_0"]
    assert len(msg) > 0


def test_hardware_registry():
    targets = load_hardware_registry()
    assert len(targets) >= 3
    ids = [t["id"] for t in targets]
    assert "rpi5-bcm2712" in ids
    assert "rpi4-bcm2711" in ids


def test_binaries_registry():
    manifest = load_binaries_registry()
    assert manifest.get("engine_type") == "llama.cpp"
    assert "arm64-a76-dotprod" in manifest.get("targets", {})
