import os
from typing import AsyncGenerator

import google.generativeai as genai

from .base import BaseModel, ModelConfig
from .claude import _build_messages


class GeminiModel(BaseModel):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.client = genai.GenerativeModel(
            model_name=self.config.model,
            generation_config={"max_output_tokens": 1024},
        )

    async def respond(self, question, history, round_num, system_prompt, show_thinking=False) -> AsyncGenerator[dict, None]:
        msgs = _build_messages(question, history, round_num, self.config.id)
        prompt = f"{system_prompt}\n\n{msgs[0]['content']}"
        response = await self.client.generate_content_async(prompt, stream=True)
        async for chunk in response:
            if chunk.text:
                yield {"type": "text", "content": chunk.text}
