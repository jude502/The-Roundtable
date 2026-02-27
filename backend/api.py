"""
FastAPI backend for The Roundtable.
Serves the frontend and handles debate sessions via SSE streaming.
"""

import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv, set_key
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI(title="The Roundtable")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
ENV_FILE = Path(__file__).parent.parent / ".env"

SYSTEM_PROMPT = """You are a participant in The Roundtable — a structured intellectual debate between multiple AI models.

RULES:
- Be direct, substantive, and confident in your views
- In round 1: give your best answer to the question. Be thorough but concise (2-4 paragraphs)
- In round 2+: engage directly with what others said. Quote them if useful. Agree, disagree, or nuance their points with specific reasoning
- Never be sycophantic — don't compliment other models' answers
- It's okay to say another model is wrong if you think they are
- Stay intellectually honest — acknowledge genuine uncertainty
- No bullet points. Write in flowing prose like a thoughtful person in a debate"""


def _get_model_instance(model_id: str):
    from backend.models.base import MODELS
    config = MODELS.get(model_id)
    if not config:
        return None
    if config.provider == "anthropic":
        from backend.models.claude import ClaudeModel
        return ClaudeModel(config)
    elif config.provider == "openai":
        from backend.models.gpt import GPTModel
        return GPTModel(config)
    elif config.provider == "google":
        from backend.models.gemini import GeminiModel
        return GeminiModel(config)
    elif config.provider == "xai":
        from backend.models.grok import GrokModel
        return GrokModel(config)
    elif config.provider == "groq":
        from backend.models.llama import LlamaModel
        return LlamaModel(config)
    return None


def _key_available(provider: str) -> bool:
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "google":    "GOOGLE_API_KEY",
        "xai":       "XAI_API_KEY",
        "groq":      "GROQ_API_KEY",
    }
    return bool(os.getenv(key_map.get(provider, ""), "").strip())


# ── SSE debate stream ─────────────────────────────────────────────────────────

async def _stream_one_model(model, question, history, round_num, show_thinking, queue):
    """Run a single model and push events into a shared asyncio Queue."""
    full_response = ""
    try:
        await queue.put({"type": "model_start", "model_id": model.config.id,
                         "model_name": model.config.name, "color": model.config.color,
                         "avatar": model.config.avatar, "round": round_num})
        async for chunk in model.respond(question, history, round_num, SYSTEM_PROMPT, show_thinking):
            if chunk["type"] == "thinking_start":
                await queue.put({"type": "thinking_start", "model_id": model.config.id})
            elif chunk["type"] == "text_start":
                await queue.put({"type": "text_start", "model_id": model.config.id})
            elif chunk["type"] == "thinking":
                await queue.put({"type": "thinking_token", "model_id": model.config.id, "token": chunk["content"]})
            elif chunk["type"] == "text":
                full_response += chunk["content"]
                await queue.put({"type": "token", "model_id": model.config.id, "token": chunk["content"]})
    except Exception as e:
        await queue.put({"type": "error", "model_id": model.config.id, "message": str(e)})
        full_response = f"[Error: {e}]"
    await queue.put({"type": "model_done", "model_id": model.config.id, "round": round_num})
    return {"model_id": model.config.id, "model_name": model.config.name,
            "content": full_response, "round": round_num}


async def _debate_generator(question: str, model_ids: list[str], rounds: int, show_thinking: bool = False):
    """
    Hybrid parallel/sequential debate:
    - Round 1: all models fire in PARALLEL (nothing to read yet)
    - Round 2+: models run SEQUENTIALLY so each reads complete prior round

    Event types: round_start | model_start | thinking_start | text_start |
                 thinking_token | token | model_done | round_done | debate_done | error
    """
    def evt(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    history: list[dict] = []

    for round_num in range(1, rounds + 1):
        yield evt({"type": "round_start", "round": round_num, "total_rounds": rounds,
                   "parallel": round_num == 1})
        round_history: list[dict] = []

        models = [_get_model_instance(mid) for mid in model_ids]
        models = [m for m in models if m]

        if round_num == 1:
            # ── PARALLEL: all models stream simultaneously into a shared queue ──
            import asyncio
            queue = asyncio.Queue()
            done_count = 0
            total = len(models)

            async def run_and_signal(m):
                result = await _stream_one_model(m, question, history, round_num, show_thinking, queue)
                await queue.put({"type": "_model_finished", "result": result})

            tasks = [asyncio.create_task(run_and_signal(m)) for m in models]

            while done_count < total:
                item = await queue.get()
                if item["type"] == "_model_finished":
                    round_history.append(item["result"])
                    done_count += 1
                else:
                    yield evt(item)

            await asyncio.gather(*tasks, return_exceptions=True)

        else:
            # ── SEQUENTIAL: each model waits for complete prior round ──
            for model in models:
                result = await _stream_one_model(model, question, history, round_num, show_thinking,
                                                  _SyncQueue())
                # For sequential we stream inline
                model_inst = model
                full_response = ""
                yield evt({"type": "model_start", "model_id": model_inst.config.id,
                           "model_name": model_inst.config.name, "color": model_inst.config.color,
                           "avatar": model_inst.config.avatar, "round": round_num})
                try:
                    async for chunk in model_inst.respond(question, history, round_num, SYSTEM_PROMPT, show_thinking):
                        if chunk["type"] == "thinking_start":
                            yield evt({"type": "thinking_start", "model_id": model_inst.config.id})
                        elif chunk["type"] == "text_start":
                            yield evt({"type": "text_start", "model_id": model_inst.config.id})
                        elif chunk["type"] == "thinking":
                            yield evt({"type": "thinking_token", "model_id": model_inst.config.id, "token": chunk["content"]})
                        elif chunk["type"] == "text":
                            full_response += chunk["content"]
                            yield evt({"type": "token", "model_id": model_inst.config.id, "token": chunk["content"]})
                except Exception as e:
                    yield evt({"type": "error", "model_id": model_inst.config.id, "message": str(e)})
                    full_response = f"[Error: {e}]"
                yield evt({"type": "model_done", "model_id": model_inst.config.id, "round": round_num})
                round_history.append({"model_id": model_inst.config.id, "model_name": model_inst.config.name,
                                      "content": full_response, "round": round_num})

        history.extend(round_history)
        yield evt({"type": "round_done", "round": round_num})

    yield evt({"type": "debate_done"})


class _SyncQueue:
    """Dummy queue for sequential path (we stream inline instead)."""
    async def put(self, _): pass


@app.get("/debate/stream")
async def debate_stream(question: str, models: str, rounds: int = 2, thinking: bool = False):
    model_ids = [m.strip() for m in models.split(",") if m.strip()]
    return StreamingResponse(
        _debate_generator(question, model_ids, rounds, show_thinking=thinking),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Models endpoint ───────────────────────────────────────────────────────────

@app.get("/models")
def get_models():
    from backend.models.base import MODELS
    return [
        {
            **vars(m),
            "available": _key_available(m.provider),
        }
        for m in MODELS.values()
    ]


# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/settings")
def get_settings():
    return {
        "ANTHROPIC_API_KEY": _mask(os.getenv("ANTHROPIC_API_KEY", "")),
        "OPENAI_API_KEY":    _mask(os.getenv("OPENAI_API_KEY", "")),
        "GOOGLE_API_KEY":    _mask(os.getenv("GOOGLE_API_KEY", "")),
        "XAI_API_KEY":       _mask(os.getenv("XAI_API_KEY", "")),
        "GROQ_API_KEY":      _mask(os.getenv("GROQ_API_KEY", "")),
    }


@app.post("/settings")
async def save_settings(body: dict):
    load_dotenv(override=True)
    ENV_FILE.touch(exist_ok=True)
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "google":    "GOOGLE_API_KEY",
        "xai":       "XAI_API_KEY",
        "groq":      "GROQ_API_KEY",
    }
    for field, env_key in key_map.items():
        val = body.get(field, "").strip()
        if val and not val.startswith("••"):
            os.environ[env_key] = val
            set_key(str(ENV_FILE), env_key, val)
    load_dotenv(override=True)
    return {"ok": True}


def _mask(val: str) -> str:
    if not val:
        return ""
    return val[:8] + "••••••••" + val[-4:] if len(val) > 12 else "••••••••"


# ── Serve frontend ────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
