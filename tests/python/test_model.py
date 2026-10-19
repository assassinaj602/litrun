import os
from litrun.model import Model
from litrun.resolver import get_model_cache_path


def test_model_load_and_generate():
    model = Model.load("qwen2.5-0.5b", allow_mock=True)
    assert model.entry.id == "qwen2.5-0.5b"
    assert model.variant is not None
    assert model.threads > 0

    response = model.generate("Hello litrun!")
    assert len(response) > 0
    assert "litrun" in response.lower()
    model.close()


def test_model_context_manager():
    with Model.load("qwen2.5-0.5b", allow_mock=True) as model:
        tokens = list(model.stream("What is edge computing?"))
        assert len(tokens) > 0
        full_text = "".join(tokens)
        assert len(full_text) > 0


def test_real_inference_if_cached():
    # If smollm2-135m weights were pre-downloaded, test real llama-server engine
    cached_path = get_model_cache_path("smollm2-135m", "q8_0")
    if not os.path.isfile(cached_path):
        cached_path = get_model_cache_path("smollm2-135m", "q4_k_m")

    if os.path.isfile(cached_path):
        with Model.load("smollm2-135m", quant="Q8_0" if "q8_0" in cached_path else "Q4_K_M", allow_mock=False) as model:
            tokens = list(model.stream("Say hello in one word."))
            assert len(tokens) > 0
            output = "".join(tokens).strip()
            assert len(output) > 0

