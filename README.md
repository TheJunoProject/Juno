<div align="center">

<img src="branding/juno-logo.png" alt="Juno" width="120" />

# Juno


A fully local, open source personal AI assistant that is always on, voice-first,
and capable of taking real actions on your behalf.

[Get Started](#getting-started) · [How It Works](#how-it-works) · [GitHub](https://github.com/Juno-Personal-AI/Juno) · [Sponsor](#sponsor)

</div>

---

## What is Juno

Juno is a personal AI assistant you actually own. It runs on your hardware,
uses open source models by default, and never sends your data anywhere you
have not explicitly chosen. You talk to it, it listens, and it gets things
done.

It is always running in the background — reading your emails, watching your
calendar, following the news you care about — so when you ask it something,
it already has the context to give you a real answer.

The closest reference point is Jarvis from Iron Man. Not a chatbot you open
and close. A system that knows your life and works for you.

---

## Features

- **Voice-first** — wake word detection, local speech-to-text, natural
  spoken responses. Hands-free by default.
- **Fully local by default** — runs entirely on open source models via Ollama.
  No cloud account required.
- **Flexible model routing** — use any combination of local and cloud models.
  Ollama, LM Studio, Anthropic, Google AI, or any OpenAI-compatible provider.
  You configure what runs where.
- **Always-on context** — a background layer continuously builds context reports
  from your email, calendar, messages, and RSS feeds. Juno knows what is
  going on before you ask.
- **Real actions** — sends messages, manages your calendar, controls your Mac,
  searches the web, reads and writes files, controls your smart home.
- **Juno Browser** — an AI-native browser built for agents. Can browse, fill
  forms, and click buttons headlessly. Can also surface pages to you in a
  clean frameless window.
- **macOS companion app** — minimal menu bar app. Hard on/off switch, markdown
  rendering, voice input, dashboard.
- **Fully private** — no telemetry, no accounts, no data leaving your machine
  unless you opt in to a cloud model.
- **Open source** — every line of code is yours to read, run, and modify.

---

## How It Works

Juno is a client/server system.

**The server** runs headlessly on any machine you choose — a dedicated mini PC,
a spare laptop, your main machine, or a hardware accelerator like a Jetson.
It handles all AI processing, agent logic, and background tasks. It exposes
a local API.

**The companion app** runs on your Mac (Linux support coming). It captures
your voice, sends requests to the server, and renders responses — spoken audio,
markdown pages, or pulled web content. It is a thin client. No AI logic lives
in the app.

```
You speak or type
      ↓
Companion app → local API → Server
      ↓
Juno's three-layer agent system processes your request
      ↓
Response back to companion app → audio / markdown / web content
```

### The Three Layers

**Interactive Layer** — the voice of Juno. Always listening. Classifies your
intent and either answers directly or dispatches work to the agentic layer.
Keeps responses fast.

**Agentic Layer** — where tasks get executed. Routes your request to the right
skills (web search, email, calendar, system control, etc.), compiles results,
and returns them.

**Background Layer** — always running silently. Checks your email and messages,
reads RSS feeds, generates context reports on your schedule. This is what
makes Juno feel like it already knows what is going on.

---

## Getting Started

> **Note:** Juno is in active early development. These instructions will be
> updated as the project matures.

### Requirements

- macOS 13+ (Linux support in progress)
- A machine to run the server (your Mac, a mini PC, a VPS, etc.)
- [Ollama](https://ollama.ai) installed for local model inference

### Install

```bash
git clone https://github.com/Juno-Personal-AI/Juno.git
cd Juno
# Setup instructions coming in Phase 1
```

### Configuration

Juno is configured via `~/.juno/config.yaml`. A full example with all options
is in `docs/config-reference.md`.

The most important section is inference routing — you control exactly which
models handle which tasks:

```yaml
inference:
  default_provider: ollama
  fallback_provider: anthropic   # optional cloud fallback

  task_routing:
    conversational: ollama
    agentic_reasoning: ollama
    complex_tasks: anthropic     # only used when you want it

  providers:
    ollama:
      base_url: http://localhost:11434
      default_model: qwen2.5:7b
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
```

---

## Recommended Stack

Juno works with any models you configure. These are the combinations that have
been tested and work well. None of these are required.

### Local Models (via Ollama)

| Task | Recommended Model | Notes |
|---|---|---|
| Conversation & reasoning | Qwen 2.5 7B | Good balance of speed and quality |
| Complex agentic tasks | Qwen 2.5 14B | More capable, needs more RAM |
| Background summarization | Phi-4 Mini | Small, fast, efficient |
| Intent classification | Phi-4 Mini or Qwen 2.5 1.5B | Fine-tunable for your patterns |
| Vision tasks | LLaVA or Moondream | For screen reading and web screenshots |

### Speech (local)

| Task | Recommended |
|---|---|
| Speech-to-text | [Whisper](https://github.com/openai/whisper) Small or Medium |
| Text-to-speech | [Kokoro](https://github.com/hexgrad/kokoro) or [Piper](https://github.com/rhasspy/piper) |
| Wake word | [openWakeWord](https://github.com/dscripka/openWakeWord) |

### Cloud Models (opt-in, API key required)

| Provider | Models | Good for |
|---|---|---|
| Anthropic | Claude Sonnet 4, Opus 4 | Complex reasoning, long context |
| Google AI | Gemini 1.5 Pro/Flash | Multimodal tasks, large context |
| Any OpenAI-compatible | — | Groq, Together, vLLM, etc. |

### Hardware

Juno runs on whatever you have. These are configurations that work well:

| Setup | Good for |
|---|---|
| Mac Mini M4 (server + client on same machine) | Simplest setup, great performance |
| Dedicated mini PC (Intel N100 or similar) + Mac | Keeps AI processing separate |
| NVIDIA Jetson Orin Nano Super (~$249) + Mac | Best performance per watt for always-on use |
| Raspberry Pi 5 + USB AI accelerator | Cheapest option, limited to small models |

---

## Fine-Tuning (Optional)

Juno works well out of the box with off-the-shelf models. If you want to
improve routing accuracy for your specific command patterns, the intent
classifier can be fine-tuned with a small LoRA on your own data.

Documentation and training scripts for this are in `docs/fine-tuning.md`.
This is entirely optional — the base system does not require it.

---

## Project Status

Juno is in active early development. The architecture is defined and Phase 1
(server foundation) is underway.

**Completed:**
- [ ] Project architecture and planning

**In Progress:**
- [ ] Phase 1 — Server foundation + local API + basic agent loop

**Planned:**
- [ ] Phase 2 — Voice pipeline
- [ ] Phase 3 — Background layer
- [ ] Phase 4 — Agentic layer + first skills
- [ ] Phase 5 — macOS system integration
- [ ] Phase 6 — Companion app polish
- [ ] Phase 7 — Memory and personalization

---

## Contributing

Juno is open source and contributions are welcome. Please read
`docs/contributing.md` before submitting a pull request.

Areas where contributions are especially valuable:
- Linux companion app (Tauri)
- Additional inference provider plugins
- New skills
- Hardware setup guides and tested configurations
- Documentation

---

## Sponsor

Juno is a solo open source project. Hardware costs money, development takes
time, and your support directly funds continued work.

If Juno is useful to you or you believe in what it is trying to do, consider
sponsoring:

**To sponser please email sponserjuno@alexbiche.me**

Every contribution helps — whether it is a one-time amount or a monthly
subscription. Thank you.

---

## License

Juno is open source. License details in `LICENSE`.

---

<div align="center">
Built in the open. Runs on your hardware. Works for you.
</div>