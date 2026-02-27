import os
from typing import AsyncGenerator

import anthropic

from .base import BaseModel, ModelConfig


class ClaudeModel(BaseModel):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def respond(
        self, question, history, round_num, system_prompt, show_thinking: bool = False
    ) -> AsyncGenerator[dict, None]:
        """
        Yields dicts: {"type": "thinking"|"text", "content": str}
        """
        messages = _build_messages(question, history, round_num, self.config.id)

        if show_thinking:
            # Extended thinking mode — streams thinking blocks then text
            async with self.client.messages.stream(
                model="claude-sonnet-4-5",
                max_tokens=16000,
                thinking={"type": "enabled", "budget_tokens": 10000},
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_start':
                            if hasattr(event, 'content_block'):
                                if event.content_block.type == 'thinking':
                                    yield {"type": "thinking_start"}
                                elif event.content_block.type == 'text':
                                    yield {"type": "text_start"}
                        elif event.type == 'content_block_delta':
                            if hasattr(event, 'delta'):
                                if event.delta.type == 'thinking_delta':
                                    yield {"type": "thinking", "content": event.delta.thinking}
                                elif event.delta.type == 'text_delta':
                                    yield {"type": "text", "content": event.delta.text}
        else:
            async with self.client.messages.stream(
                model=self.config.model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "text", "content": text}


def _build_messages(question: str, history: list[dict], round_num: int, self_id: str) -> list[dict]:
    if round_num == 1 or not history:
        return [{"role": "user", "content": f"Question for the roundtable:\n\n{question}"}]

    others = [h for h in history if h["model_id"] != self_id]
    context = "\n\n".join([
        f"**{h['model_name']}:** {h['content']}" for h in others
    ])
    return [{
        "role": "user",
        "content": (
            f"Roundtable question: {question}\n\n"
            f"Here is what the other participants said in round {round_num - 1}:\n\n"
            f"{context}\n\n"
            "Please respond to the other participants. "
            "Engage directly with their arguments — agree where you do, push back where you don't. "
            "Be direct and specific."
        )
    }]
