from litrun.session import Session, ChatMessage


def test_session_lifecycle():
    s = Session(max_context_tokens=100)
    s.add_user_message("Hello world")
    assert len(s.messages) == 1
    assert s.messages[0].role == "user"

    s.add_assistant_message("Hi there! How can I help?")
    assert len(s.messages) == 2

    chatml = s.format_prompt(family="qwen")
    assert "<|im_start|>user" in chatml
    assert "<|im_start|>assistant" in chatml

    llama = s.format_prompt(family="llama")
    assert "<|start_header_id|>user<|end_header_id|>" in llama


def test_session_pruning():
    s = Session(max_context_tokens=50)
    # Add multiple turns
    for i in range(10):
        s.add_user_message(f"Message number {i} with some long text to fill context")
        s.add_assistant_message(f"Response number {i} with even more descriptive content")

    # Should have pruned older messages to stay within budget
    assert len(s.messages) < 20
