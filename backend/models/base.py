"""
Base model interface — all providers implement this.
"""

from dataclasses import dataclass
from typing import AsyncGenerator


@dataclass
class ModelConfig:
    id: str           # internal key e.g. "claude"
    name: str         # display name e.g. "Claude"
    model: str        # API model string
    color: str        # hex color for UI
    avatar: str       # emoji avatar
    provider: str     # "anthropic" | "openai" | "google" | "xai"


# Registry of all supported models
MODELS: dict[str, ModelConfig] = {
    "claude": ModelConfig(
        id="claude", name="Claude", model="claude-sonnet-4-5",
        color="#8b5cf6", avatar="🟣", provider="anthropic",
    ),
    "gpt": ModelConfig(
        id="gpt", name="GPT-4o", model="gpt-4o",
        color="#10b981", avatar="🟢", provider="openai",
    ),
    "gemini": ModelConfig(
        id="gemini", name="Gemini", model="gemini-1.5-pro",
        color="#3b82f6", avatar="🔵", provider="google",
    ),
    "grok": ModelConfig(
        id="grok", name="Grok", model="grok-beta",
        color="#f59e0b", avatar="🟡", provider="xai",
    ),
    "llama": ModelConfig(
        id="llama", name="Llama", model="llama-3.3-70b-versatile",
        color="#e5e7eb", avatar="⚪", provider="groq",
    ),
}


class BaseModel:
    def __init__(self, config: ModelConfig):
        self.config = config

    async def respond(
        self,
        question: str,
        history: list[dict],  # [{"model_id": ..., "model_name": ..., "content": ...}]
        round_num: int,
        system_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Stream a response token by token."""
        raise NotImplementedError
