# Juno — Project Context for Claude Code

## What is Juno?

Juno is a fully local, private, Jarvis-style personal AI assistant. It is built on top of a forked and heavily modified version of OpenClaw, an open source agentic AI runtime. The goal is a system that feels like a genuine personal AI — always on, context-aware, capable of acting on your behalf across your devices, your communications, the web, and your physical environment.

---

## Core Principles

- **Fully private** — everything runs locally by default. Cloud models (Claude, Gemini) are an opt-in escape hatch for complex tasks only, never the default
- **Single user** — this is not a multi-tenant or workspace product. It is built for one person
- **Always on** — the system runs continuously in the background, proactively building context and ready to respond instantly
- **Open source** — 100% MIT licensed, no telemetry, no hidden behaviors, fully auditable
- **Relatively cheap** — designed to run on consumer hardware, not data center infrastructure

---

## Hardware Architecture

Juno runs across two physical devices:

**Backend Box (the brain)**
A Jetson Orin Nano Super or similar edge AI device acting as the always-on server. Runs small, continuous models — wake word detection, STT, TTS, intent classification, background summarization. Low power, always on.

**Mac (the hands)**
A MacBook Air M4 or Mac Mini M4. This is where Juno takes actions — controlling apps, reading the screen, sending messages, managing files. The Mac Mini M4's unified memory architecture also makes it capable of running larger local models (7B–14B) on demand via Ollama.

---

## Three-Layer Architecture

### Interactive Layer
The interface between Juno and the user. Always on, responds quickly, routes tasks.

**Pipeline:**
```
Voice/text input
      ↓
Wake word detection (openWakeWord — tiny, always on)
      ↓
Speech-to-text (Whisper Small — local)
      ↓
Intent classifier (fine-tuned Phi-4 Mini or Qwen 2.5 1.5B — LoRA)
      ↓
  Path A: Simple query → conversational model answers directly (Qwen 2.5 7B)
  Path B: Complex task → dispatches to Agentic Layer
      ↓
Response assembled + TTS (Kokoro or Piper — local)
      ↓
Spoken/displayed output via macOS companion app
```

**Responsibilities:**
- Read and use context reports produced by the Background Layer
- Route intent to the correct path or agent
- Deliver final responses to the user
- Maintain conversational continuity

### Agentic Layer
Where tasks get executed. May use cloud models for complex reasoning.

**Pipeline:**
```
Task received from Interactive Layer
      ↓
Task router — which skill(s) are needed?
      ↓
Skill execution (web, email, files, system control, etc.)
      ↓
Results compiled
      ↓
Summarizer — condenses results for Interactive Layer
      ↓
Response sent back up
```

**Responsibilities:**
- Execute complex multi-step tasks
- Manage skill/tool calls with defined input/output schemas
- Decide when local model suffices vs. escalating to cloud (Claude Sonnet 4 → Opus 4)
- Report results back to the Interactive Layer cleanly

**Cloud escalation rule:** if the local model fails or produces low-confidence output after 2 attempts, escalate to Claude Sonnet 4. Reserve Opus 4 for genuinely complex reasoning tasks. Always prefer local.

### Background Layer
Silent, always-on context engine. Never talks to the user directly.

**Scheduled jobs:**
```
Every 15 min  → Check email and messages for urgent items
Every 1 hour  → RSS feeds → summarize new items
Every 6 hours → Full context report generation
On trigger    → Urgent interrupt pushed to Interactive Layer
      ↓
Context reports written to structured markdown/JSON files
      ↓
Interactive Layer reads these at the start of every conversation
```

**Responsibilities:**
- Produce structured context reports covering: news, email digest, messages, calendar, reminders, active projects
- Flag urgent items and interrupt the Interactive Layer when needed
- Run entirely on small local models (Phi-4 Mini, Qwen 2.5 3B)
- Never call cloud APIs — must be lightweight and always on

---

## Memory Architecture

Juno maintains three types of memory:

**Context Reports** — produced by the Background Layer, short-lived, reflect current state of the world (email, news, calendar). Stored as structured markdown files.

**Conversation Memory** — key facts extracted from every conversation and stored persistently. Example: "User has a dentist appointment Friday." Retrieved via lightweight semantic search at conversation start. Stack: ChromaDB or SQLite-vec, fully local.

**Long-term Knowledge Store** — preferences, project history, learned behaviors. Periodically consolidated and summarized to avoid unbounded growth.

---

## Skill Stack

Skills are the tools the Agentic Layer can call. Each skill has a defined input/output schema. They are modular — new skills can be added without touching core logic.

**Planned skills:**
- **Juno Browser** — AI-native Chromium browser via Playwright. Two modes: Agent Mode (headless, agent drives) and Display Mode (clean frameless window surfaced in companion app). Agent sees page as text + interactive element map + screenshot simultaneously.
- **Email Manager** — connects to Mail.app via AppleScript/IMAP. Background polling, urgency classification, draft and send with user confirmation.
- **Communications** — iMessage/SMS via AppleScript → Messages.app. Phone call initiation via macOS/iPhone handoff.
- **Calendar & Scheduling** — EventKit via Swift helper or AppleScript → Calendar.app. Full read/write access.
- **System Controller** — app launch/quit, window management, Do Not Disturb, volume/brightness, screenshot + vision analysis, clipboard read/write, file operations. Via AppleScript + macOS Accessibility API.
- **Smart Home** — HomeKit API via Swift helper, or Home Assistant if running locally.
- **Research Tool** — multi-step research agent using Juno Browser. Returns structured briefings, not just links.
- **Reminders & Proactive Alerts** — time-based and event-based triggers. Juno reaches out to the user, not the other way around.
- **Clipboard Intelligence** — summarize, rewrite, translate, fix clipboard content and optionally paste back.

---

## Local Model Stack

| Job | Model | Runs on |
|---|---|---|
| Wake word | openWakeWord | Jetson / Pi |
| STT | Whisper Small | Jetson |
| TTS | Kokoro or Piper | Jetson |
| Intent classifier | Phi-4 Mini (LoRA fine-tuned) | Jetson |
| Conversational | Qwen 2.5 7B | Mac (Ollama) |
| Agentic reasoning | Qwen 2.5 14B | Mac (Ollama) |
| Background summarizer | Phi-4 Mini | Jetson |
| Vision / hand tracking | MediaPipe | Jetson |
| Cloud escape hatch | Claude Sonnet 4 / Opus 4 | API only |

---

## UI

The macOS companion app is the primary user-facing interface. It is not a chat app wrapper — it is a purpose-built control surface for Juno.

**Key UI requirements:**
- Hard on/off switch — pressing it fully shuts down or starts all Juno processes instantly
- Displays Juno responses in clean markdown-rendered output
- Hosts the Display Mode viewport for Juno Browser — frameless, no browser chrome, just the page with a minimal floating Juno control bar
- Surfaces proactive alerts and notifications from the Background Layer
- Stays out of the way when not needed

---

## Codebase Origin

Juno is forked from OpenClaw (https://github.com/openclaw/openclaw.git). The following has been stripped from the original:

- All third-party messaging channel integrations (WhatsApp, Telegram, Discord, Slack, Signal, iMessage via OpenClaw, Matrix, Teams, IRC, and all others)
- Multi-user and workspace management
- Community skill marketplace / registry
- Telemetry and analytics
- OpenClaw/Molty branding throughout

The following has been kept and forms the Juno core runtime:

- Skill execution engine
- Ollama local model integration
- Session and memory management
- macOS node hooks
- Core agent runtime loop

---

## Development Approach

- The primary developer uses Claude Code for implementation
- Architecture and product decisions are made by the human, implementation is handled by Claude Code
- Build order: Background Layer first → Interactive Layer → Agentic Layer → macOS companion app → individual skills
- Start with stubs for skills, expand one at a time
- Fine-tuning and LoRA are in scope — the intent classifier is the highest priority fine-tune
- TypeScript is the primary language (inherited from OpenClaw base)
- All new code should be clean, well-commented, and modular — future contributors should be able to read it easily

---

## What NOT to Do

- Do not add multi-user features
- Do not add third-party messaging channel integrations
- Do not make cloud API calls from the Background Layer
- Do not call Opus 4 for simple tasks — it is expensive and reserved for hard problems
- Do not store sensitive data (credentials, personal info) anywhere except the local encrypted keychain
- Do not add telemetry of any kind
