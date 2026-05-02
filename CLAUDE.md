# Juno — Technical Context for Claude Code

This file is the authoritative reference for all development work on Juno.
Read it fully before writing any code, creating any files, or making any
architectural decisions. When in doubt, refer back here.

---

## What is Juno

Juno is a fully local, private, open source personal AI assistant built from
scratch. It is a client/server system: a headless server that runs all AI
and agent logic, and a companion app that acts as the user interface. The two
communicate over a local API.

The design goal is a system that feels like a genuine intelligent presence —
always on, voice-first, context-aware, capable of taking actions on the user's
behalf across their devices, communications, and the internet.

---

## Repository Structure

```
juno/
  server/               ← Headless brain — runs on any local machine
    api/                ← REST + WebSocket API (local network only)
    agents/             ← Three-layer agent system
      interactive/      ← Voice/text in, intent routing, response out
      agentic/          ← Task execution, skill dispatch, tool calls
      background/       ← Scheduled context building, always running
    skills/             ← Individual tool modules (one dir per skill)
      browser/          ← Juno Browser (Playwright + Chromium)
      email/
      calendar/
      communications/
      system/
      research/
      smart-home/
      reminders/
      clipboard/
    inference/          ← Unified model inference abstraction layer
      providers/        ← One plugin per inference backend
    memory/             ← Context reports, conversation memory, knowledge store
    scheduler/          ← Cron-style job runner for background layer
    config/             ← User configuration schema and loader
  companion/            ← Client UI
    macos/              ← SwiftUI app (primary)
    linux/              ← Tauri app (secondary)
  docs/                 ← Project documentation
  hardware/             ← Optional: setup guides, 3D print files
  LICENSE
  README.md
  CLAUDE.md             ← This file
```

---

## Architecture

### Client / Server Split

The system is strictly split. The companion app contains zero AI logic.

**Server responsibilities:**
- Receive requests from the companion app via local API
- Run the three-layer agent system
- Interface with AI models through the unified inference layer
- Execute skills and tool calls
- Run scheduled background jobs
- Maintain all memory and context stores
- Return structured responses to the companion app

**Companion app responsibilities:**
- Capture voice (send audio to server) or text input
- Send requests to the server API
- Receive responses and render them:
  - Play TTS audio
  - Render markdown pages
  - Display web elements (pulled by server, rendered by client)
- Surface proactive alerts and notifications from the server
- Provide the on/off switch that starts/stops server processes
- Act as dashboard for active tasks and context summaries

The companion app is a thin client. It does not make model calls. It does not
run skills. All intelligence is on the server.

### Local API

Server exposes two interfaces on the local network:

- **REST** — request/response for most interactions (send message, get status,
  toggle settings)
- **WebSocket** — streaming for real-time response delivery and server-pushed
  proactive alerts from the background layer

The API is local only. It is never exposed to the internet.

### Request Flow

```
User speaks or types
      ↓
Companion app captures input (audio file or text string)
      ↓
POST /api/input → server
      ↓
Interactive Layer processes (STT if audio, intent classification, routing)
      ↓
  Path A — Simple: model answers directly, reads context reports
  Path B — Complex: Agentic Layer executes task via skills
      ↓
Response + data returned to companion app
      ↓
Companion app renders response (audio / markdown / web element / combination)
```

---

## Three-Layer Agent System

All agent logic lives on the server. Layers are distinct modules that
communicate via internal interfaces, not direct calls.

### Interactive Layer (`server/agents/interactive/`)

Always running. The user-facing layer.

**Input:** voice audio or text string from companion app
**Output:** structured response object (text + TTS audio + optional markdown
page or web element reference)

**Processing pipeline:**
1. If audio input: STT transcription
2. Intent classification — determines path A or B
3. Path A (simple): load relevant context reports from memory store, query
   conversational model, return response
4. Path B (complex): package task + context, dispatch to Agentic Layer, wait
   for result, assemble final response
5. TTS synthesis on response text
6. Return to companion app

**Key constraints:**
- Must respond quickly — this is what the user is waiting on
- Reads context reports at the start of every interaction
- Maintains conversational continuity across turns within a session
- Intent classifier is the most critical component — wrong routing is the
  most common failure mode

### Agentic Layer (`server/agents/agentic/`)

Executes tasks. Receives a task description + context from the Interactive
Layer, executes it using skills, returns a structured result.

**Processing pipeline:**
1. Parse task and determine which skill(s) are needed
2. Execute skills (sequentially or in parallel depending on task)
3. Compile results
4. Summarize into clean response for the Interactive Layer
5. Return structured result

**Key constraints:**
- Each skill call must use the defined input/output schema — no freeform calls
- Cloud model escalation: local model gets 2 attempts by default, then
  escalates to configured fallback provider. Threshold is user-configurable.
- Must report failures cleanly — never silently fail
- Skill execution is sandboxed where possible

### Background Layer (`server/agents/background/`)

Silent, always-on context engine. Produces context reports that make the
Interactive Layer feel context-aware.

**Scheduled jobs (defaults, all user-configurable):**
- Every 15 min: email and messages check, flag urgent items
- Every 1 hour: RSS feed fetch and summarize
- Every 6 hours: full context report generation
- On event: push urgent interrupt to Interactive Layer via internal event bus

**Output:** structured context report files written to `memory/reports/`:
- `email-digest.md`
- `calendar.md`
- `messages.md`
- `news.md`
- `projects.md`
- `reminders.md`

**Key constraints:**
- Must use only small, fast local models — cannot be a resource drain
- Never calls cloud APIs — must be fully local and always running
- Context report format must be consistent so the Interactive Layer can parse
  it reliably

---

## Inference Layer (`server/inference/`)

### Design

All model calls in the entire system go through one abstraction: the inference
layer. No agent, skill, or background job ever calls a model provider directly.

This means:
- Model providers are plugins — adding or swapping one never requires changing
  agent code
- The user can configure any combination of local and cloud models per task
  type
- The routing logic (which model handles which task) is fully user-configurable

### Provider Plugin Interface

Each provider implements a common interface:

```typescript
interface InferenceProvider {
  id: string                    // e.g. "ollama", "anthropic", "openai-compat"
  name: string                  // human readable
  isAvailable(): Promise<boolean>
  complete(request: InferenceRequest): Promise<InferenceResponse>
  stream(request: InferenceRequest): AsyncIterator<InferenceChunk>
}
```

### Built-in Providers (implement in this order)

1. **Ollama** — local inference via Ollama API. Primary provider.
2. **OpenAI-compatible** — covers any provider with an OpenAI-compatible
   endpoint (LM Studio, vLLM, Together, Groq, etc.)
3. **Anthropic** — Claude models via Anthropic API
4. **Google AI** — Gemini models via Google AI API

### Routing Classifier

A small, fast classifier model (runs locally, always on) handles routing
decisions: given a task type and the user's configuration, which provider
and model should handle this request?

The classifier lives at `server/inference/router/` and respects:
- User's configured preferences per task type
- Provider availability (health checks — if Ollama is unreachable, fall back)
- Cost policy (user sets "prefer local", "allow cloud", or per-task overrides)
- Escalation state (has local already failed for this request?)

This is a plugin in the inference layer, not a hardcoded rule chain.

### User Configuration

All inference routing is configured in `~/.juno/config.yaml`:

```yaml
inference:
  default_provider: ollama
  fallback_provider: anthropic
  escalation_attempts: 2

  task_routing:
    conversational: ollama
    agentic_reasoning: ollama
    background_summarization: ollama
    complex_tasks: anthropic

  providers:
    ollama:
      base_url: http://localhost:11434
      default_model: qwen2.5:7b
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
      default_model: claude-sonnet-4-5
```

No model names are hardcoded anywhere in agent or skill code.
All model references come from config.

---

## Skill System (`server/skills/`)

### Design

Each skill is a self-contained module with:
- A manifest (`skill.json`) declaring name, description, input schema,
  output schema
- An implementation file containing the execution logic
- Optional per-skill configuration

Skills are discovered at server startup by scanning `server/skills/`.
The Agentic Layer calls skills by name with a typed input object and receives
a typed output object. Skills never call models directly — if a skill needs
a model, it goes through the inference layer.

### Skill Interface

```typescript
interface Skill {
  name: string
  description: string
  inputSchema: JSONSchema
  outputSchema: JSONSchema
  execute(input: SkillInput, context: SkillContext): Promise<SkillOutput>
}
```

### Skill Manifest (`skill.json`)

```json
{
  "name": "web_search",
  "description": "Search the web and return structured results",
  "input": {
    "query": { "type": "string", "required": true },
    "max_results": { "type": "number", "required": false }
  },
  "output": {
    "results": { "type": "array" },
    "summary": { "type": "string" }
  }
}
```

### Skills Build Order

1. `browser` — Juno Browser (see dedicated section)
2. `web_search` — uses browser in agent mode, returns structured results
3. `file_read` / `file_write` — read/write files
4. `clipboard` — read/write/transform Mac clipboard
5. `system` — Mac system control (apps, windows, DND, screenshot, volume)
6. `email` — Mail.app via AppleScript or IMAP
7. `calendar` — Calendar.app via EventKit Swift helper
8. `messages` — iMessage/SMS via AppleScript
9. `reminders` — time/event-based alerts with proactive push
10. `research` — multi-step loop using browser skill
11. `smart_home` — HomeKit or Home Assistant

---

## Juno Browser (`server/skills/browser/`)

The most complex skill. An AI-native browser built on Playwright + Chromium.

### Agent Mode (headless)

For each page load, three parallel extractions:
1. **Clean text/markdown** via Readability.js — for reading content
2. **Interactive element map** — all actionable elements (buttons, inputs,
   links, selects) with IDs and coordinates, extracted from Playwright's
   accessibility tree. This is the primary action interface — do not rely
   on vision for clicking.
3. **Screenshot** — for visual confirmation when needed, passed to vision
   model if configured

Agent actions: `click(elementId)`, `type(elementId, text)`,
`scroll(direction)`, `navigate(url)`, `submit(formId)`, `extract(selector)`

### Display Mode

Server instructs companion app to open a frameless browser window at a URL.
Companion renders the page with no browser chrome — content only, with a
minimal floating Juno control bar. User interacts naturally. Agent can still
see and act on the same page (shared page context).

### Stack
- Playwright (automation layer)
- Chromium (engine — best compatibility, best Playwright support)
- Readability.js (content extraction)
- Playwright accessibility tree API (element map — preferred over screenshot
  for action targeting)

---

## Memory System (`server/memory/`)

### Three Stores

**Context Reports** (`memory/reports/`)
- Produced by Background Layer on schedule
- Structured markdown, one file per domain
- Read by Interactive Layer at session start
- Short-lived — overwritten on each generation cycle

**Conversation Memory** (`memory/conversations/`)
- Key facts extracted from every conversation and persisted
- Retrieved via local vector search at session start
- Periodically consolidated to control growth
- Implementation: ChromaDB or SQLite-vec — fully local, no external service

**Knowledge Store** (`memory/knowledge/`)
- Long-term preferences, learned behaviors, user-defined facts
- Append-only with periodic summarization
- Structured JSON

### Vector Search
Fully local. ChromaDB running locally or SQLite with sqlite-vec extension.
No external vector database services.

---

## Configuration System (`server/config/`)

Single YAML or TOML config file at `~/.juno/config.yaml`.
Validated against a schema on every server start.
Invalid config produces a clear error message, never a silent crash.

Key areas:
- Inference provider setup and per-task routing
- Background layer job schedules
- Enabled skills
- Wake word sensitivity
- Memory retention policies
- Companion app connection settings

---

## Companion App

### macOS (`companion/macos/`) — SwiftUI
Menu bar app with floating window. Primary platform.

Responsibilities (all, no exceptions):
- Voice capture → audio file → POST to server API
- Text input → POST to server API
- Audio playback of TTS responses
- Markdown rendering
- Frameless web view for Juno Browser display mode
- Dashboard: active tasks, context summaries, notification feed
- Hard on/off: calls server API to start/stop all Juno processes
- WebSocket connection to server for streaming responses and push alerts

### Linux (`companion/linux/`) — Tauri
Functionally equivalent. Tauri over Electron for lower resource usage.

### Hard rule
The companion app must never contain inference calls, skill execution, agent
logic, or memory management. If logic creeps into the companion app, move it
to the server.

---

## Scheduler (`server/scheduler/`)

Built-in cron-style scheduler. Must:
- Support cron expressions for recurring jobs
- Support one-off delayed jobs (reminders)
- Support event-driven triggers (background layer urgent interrupts)
- Persist job state across server restarts
- Expose an internal event bus for inter-layer communication

The interrupt path for Background Layer → Interactive Layer → Companion App:
```
Background layer emits event on internal bus
      ↓
Interactive layer receives event, packages alert
      ↓
Server pushes to companion app via WebSocket
      ↓
Companion app surfaces notification + optional audio alert
```

---

## Development Rules

### Always
- Validate all config on load
- Route all model calls through the inference layer — never call a provider
  directly from agent or skill code
- Use typed skill interfaces for all tool calls from the Agentic Layer
- Keep the companion app as a thin client
- Handle provider unavailability gracefully — always have a defined fallback
- Write typed interfaces for all inter-layer communication

### Never
- Call cloud APIs from the Background Layer
- Store credentials anywhere except the OS keychain
- Add telemetry, analytics, or any form of data reporting
- Add multi-user features
- Add Windows support
- Add third-party messaging channel integrations (WhatsApp, Telegram, Discord,
  Slack, etc.)
- Expose the local API to the internet
- Hardcode model names, provider URLs, or API keys in source code

### Language / Runtime
**TBD — must be decided before Phase 1.** Options:
- Python + FastAPI (richer ML ecosystem, simpler Ollama/Whisper integration)
- TypeScript + Fastify/Node (stronger typing, better if sharing code patterns
  with SwiftUI companion)

Record the decision in this file and do not revisit it.

macOS companion: SwiftUI
Linux companion: Tauri

### Build Order
Complete each phase end-to-end before starting the next.

1. Server foundation — API, inference layer (Ollama only), basic agent loop,
   minimal text-only companion
2. Voice pipeline — STT, TTS, wake word, audio I/O
3. Background layer — scheduler, email + RSS jobs, context reports, read by
   Interactive Layer
4. Agentic layer + first skills — intent classifier, task router, skill engine,
   web search + file + clipboard
5. macOS system integration — system controller, email, calendar, messages
6. Companion app polish — markdown, display mode, dashboard, notifications,
   on/off switch
7. Memory — conversation memory, vector retrieval, knowledge store
8. Fine-tuning (optional) — intent classifier LoRA, documented process

---

## Open Questions (resolve before Phase 1)

1. **Server runtime** — Python (FastAPI) or TypeScript (Fastify)? Decide,
   record here, do not revisit.
2. **Linux companion** — Tauri or Electron?
3. **STT placement** — server-side (keeps companion thin, adds audio streaming
   latency) or companion-side (lower latency, adds dependency)? Plan config
   to support both.

---

## License

License is TBD — either a custom license or GNU GPL v3. Not MIT.
Do not add any license headers to files until this is decided.