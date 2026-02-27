# The Roundtable

> Pose a question. Watch frontier AI models debate each other in real time.

The Roundtable connects Claude, GPT-4o, Gemini, and Grok into a single conversation — each model answers independently, then reads the others' responses and replies directly. You watch it stream live.

![The Roundtable](https://img.shields.io/badge/models-Claude_%7C_GPT--4o_%7C_Gemini_%7C_Grok-8b5cf6?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-10b981?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11+-3b82f6?style=flat-square)

---

## What it does

1. You type a question
2. Each selected model answers simultaneously (Round 1)
3. Each model reads the others' answers and responds directly (Round 2, 3...)
4. Everything streams token-by-token in real time

Works for physics questions, philosophy, engineering tradeoffs, medical second opinions, legal arguments — anything where multiple perspectives add value.

---

## Setup

**Requires Python 3.11+ and Node.js**

```bash
# Clone
git clone https://github.com/jude502/The-Roundtable.git
cd The-Roundtable

# Install Python deps
python3 -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your API keys to .env (or use the in-app Settings panel)
```

### Run as desktop app (recommended)
```bash
cd electron
npm install
npm start
```

### Run in browser
```bash
python3 main.py
# then open http://localhost:8080
```

---

## API Keys

You need at least one key to use the app. Add keys in-app via the Settings gear, or paste them into `.env`:

| Model | Provider | Get your key |
|---|---|---|
| Claude | Anthropic | [console.anthropic.com](https://console.anthropic.com) |
| GPT-4o | OpenAI | [platform.openai.com](https://platform.openai.com) |
| Gemini | Google | [aistudio.google.com](https://aistudio.google.com) |
| Grok | xAI | [console.x.ai](https://console.x.ai) |

Keys are stored locally in `.env` and never leave your machine.

---

Cost

Each debate session costs roughly:

| Setup | Estimated cost |
-------------------------------
| 4 models, 1 round | ~$0.02 |
| 4 models, 2 rounds | ~$0.07 |
| 4 models, 3 rounds | ~$0.18 |

Negligible for personal use.

---

## Project Structure

```
theroundtable/
├── main.py                  # Entry point
├── backend/
│   ├── api.py               # FastAPI server + SSE streaming
│   └── models/
│       ├── base.py          # Model interface + registry
│       ├── claude.py        # Anthropic client
│       ├── gpt.py           # OpenAI client
│       ├── gemini.py        # Google client
│       └── grok.py          # xAI client
└── frontend/
    ├── index.html           # Main UI
    └── static/
        ├── style.css
        └── app.js
```

---

## Adding a new model

1. Add a `ModelConfig` entry to `backend/models/base.py`
2. Create a new client file in `backend/models/` implementing `BaseModel.respond()`
3. Add the provider case to `_get_model_instance()` in `backend/api.py`

---

## License

MIT — do whatever you want with it.
