from litrun.model import Model


def test_model_load_and_generate():
    model = Model.load("qwen2.5-0.5b", allow_mock=True)
    assert model.entry.id == "qwen2.5-0.5b"
    assert model.variant is not None
    assert model.threads > 0

    response = model.generate("Hello litrun!")
    assert len(response) > 0
    assert "litrun" in response.lower()


def test_model_stream():
    model = Model.load("qwen2.5-0.5b", allow_mock=True)
    tokens = list(model.stream("What is edge computing?"))
    assert len(tokens) > 0
    full_text = "".join(tokens)
    assert len(full_text) > 0
