import os
from typing import AsyncGenerator

from openai import AsyncOpenAI  # xAI uses OpenAI-compatible API

from .base import BaseModel, ModelConfig
from .claude import _build_messages


class GrokModel(BaseModel):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1",
        )

    async def respond(self, question, history, round_num, system_prompt, show_thinking=False) -> AsyncGenerator[dict, None]:
        messages = [{"role": "system", "content": system_prompt}]
        messages += _build_messages(question, history, round_num, self.config.id)
        stream = await self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=1024,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield {"type": "text", "content": delta}
