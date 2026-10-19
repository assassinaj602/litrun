"""
litrun Session & Context Window Manager
Manages multi-turn conversation state, token budget truncation, and chat templates.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Literal


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class Session:
    system_prompt: str = "You are a helpful, concise AI assistant running on embedded Linux."
    messages: List[ChatMessage] = field(default_factory=list)
    max_context_tokens: int = 2048

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))
        self.prune_context_if_needed()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="assistant", content=content))
        self.prune_context_if_needed()

    def clear(self) -> None:
        self.messages.clear()

    def estimate_tokens(self, text: str) -> int:
        """Rough heuristic: ~4 characters per token for English text."""
        return max(1, len(text) // 4)

    def total_estimated_tokens(self) -> int:
        total = self.estimate_tokens(self.system_prompt)
        for msg in self.messages:
            total += self.estimate_tokens(msg.content) + 4
        return total

    def prune_context_if_needed(self) -> None:
        """Keeps conversation within max_context_tokens by pruning oldest user/assistant pairs."""
        while len(self.messages) > 2 and self.total_estimated_tokens() > (self.max_context_tokens - 256):
            # Drop the oldest turn (index 0 and index 1 if available)
            self.messages.pop(0)

    def format_prompt(self, family: str = "qwen") -> str:
        """
        Formats conversation history using standard chat templates:
        - ChatML: Qwen, SmolLM
        - Llama-3 format: Llama 3 / 3.2
        """
        family_clean = family.lower()

        if "llama" in family_clean:
            # Llama 3 format
            lines = ["<|begin_of_text|>"]
            if self.system_prompt:
                lines.append(f"<|start_header_id|>system<|end_header_id|>\n\n{self.system_prompt}<|eot_id|>")
            for msg in self.messages:
                lines.append(f"<|start_header_id|>{msg.role}<|end_header_id|>\n\n{msg.content}<|eot_id|>")
            lines.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
            return "".join(lines)
        else:
            # ChatML (Qwen, SmolLM, Phi)
            lines = []
            if self.system_prompt:
                lines.append(f"<|im_start|>system\n{self.system_prompt}<|im_end|>\n")
            for msg in self.messages:
                lines.append(f"<|im_start|>{msg.role}\n{msg.content}<|im_end|>\n")
            lines.append("<|im_start|>assistant\n")
            return "".join(lines)
