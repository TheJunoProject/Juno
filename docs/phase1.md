# Phase 1 — Server Foundation

Status: complete (2026-05-02).

Phase 1 is the thinnest possible end-to-end working system: a server that
accepts a text message from a client, sends it to a local model via Ollama,
and streams the response back. Everything later phases need to build on lives
here.

---

## What was built

### Runtime decision: Python 3.11+ with FastAPI

Recorded in [CLAUDE.md](../CLAUDE.md#language--runtime). Reasoning:

- Every downstream phase pulls in Python-native tooling (Whisper, Kokoro /
  Piper, openWakeWord, ChromaDB / sqlite-vec, optional LoRA fine-tuning).
- The companion is SwiftUI / Tauri, so there is no shared-language benefit
  to TypeScript on the server.
- FastAPI gives first-class WebSocket streaming. Pydantic v2 closes most of
  the type-safety gap with TypeScript.
- The official `ollama` Python client and the wider local-AI ecosystem are
  Python-first.

### Repository structure

Matches the canonical layout in CLAUDE.md. Phase 1 only touches `server/`,
`tests/`, `docs/`, and the top-level scaffolding (`pyproject.toml`,
`.gitignore`, `client.py`). All other directories from the spec exist as
empty placeholders.

```
server/
  api/                 REST + WebSocket
    routes/            chat, health, admin
    app.py             FastAPI factory + lifespan
    models.py          wire-format Pydantic models
    logging.py         logging setup + access middleware
  agents/
    interactive/       layer.py, prompts.py, sessions.py
    agentic/           (placeholder)
    background/        (placeholder)
  inference/
    base.py            InferenceProvider, request/response/chunk types
    router.py          config-driven dispatch + fallback
    providers/
      ollama.py        Ollama HTTP provider (httpx-based)
  memory/
    reports.py         load context reports for system prompt
  config/
    schema.py          typed Pydantic schema
    loader.py          load + validate + first-run default generation
    defaults.py        commented default config text
  scheduler/           (placeholder)
  skills/              (placeholder)
  cli.py               `juno start`, `juno init-config`
  __main__.py          `python -m server`
client.py              Phase 1 smoke-test WebSocket client
tests/                 pytest suite (15 passing, 1 skipped)
```

### Configuration

- Lives at `~/.juno/config.yaml`. Generated with sensible commented defaults
  on first run.
- Validated with Pydantic v2 on every server start.
- Invalid YAML, unknown fields, and out-of-range values all produce a
  human-readable error pointing at the field — never a stack trace.
- `JUNO_CONFIG` env var overrides the path (used by tests; useful for ops).
- `extra="forbid"` everywhere: typos in keys are validation errors, not
  silent ignores.

### Inference layer

The contract every model call in Juno goes through:

```python
class InferenceProvider:
    id: str
    name: str
    async def is_available(self) -> bool
    async def complete(self, request) -> InferenceResponse
    def stream(self, request) -> AsyncIterator[InferenceChunk]
    async def aclose(self) -> None
```

- Phase 1 ships one provider, **Ollama**, talking to `/api/chat` over httpx.
  Streaming is real (NDJSON parsed line-by-line, not buffered).
- `InferenceRouter` dispatches on `task_type` per the config. Adding a new
  provider is a new file in `server/inference/providers/` plus one line in
  `InferenceRouter._build_providers`. No agent / skill code changes.
- `complete()` retries on the primary provider up to
  `escalation_attempts` times, then falls back to `fallback_provider`
  (when configured) — none configured by default in Phase 1.
- `stream()` does **not** retry: switching providers mid-stream would
  produce a corrupt response after the first chunk hits the wire.
- Provider unavailability is non-fatal at startup. The server logs a
  warning, `/api/health` reflects the state, and chat requests get a
  clean 502 until Ollama comes back up.

### Interactive layer

- `handle_text(message, session_id?)` for one-shot, `stream_text(...)` for
  streaming.
- Builds the prompt from: persona system prompt + rendered context reports
  (loaded fresh per turn from `memory/reports/`, empty in Phase 1) + session
  history + the new user turn.
- Session history is in-process LRU (max 256 sessions, max 40 messages
  each). Persistence and vector retrieval land in Phase 7.
- Designed for extension, not rewrite, in Phases 2/3/4: STT/TTS at the API
  boundary, intent classification as a routing step before the inference
  call, agentic dispatch as an alternative to the direct conversational
  path.

### REST + WebSocket API

| Endpoint                | Purpose                                            |
| ----------------------- | -------------------------------------------------- |
| `GET  /api/health`      | Provider availability + configured model           |
| `POST /api/chat`        | One-shot chat                                      |
| `WS   /api/chat/stream` | Streaming chat. Server sends one JSON frame per chunk, then `{"done": true}`. |
| `POST /api/shutdown`    | Graceful stop (used by future companion on/off)    |

- Binds to `127.0.0.1` by default. The config schema accepts other hosts
  but the default config and the docs explicitly warn against it.
- All errors are JSON, never HTML.
- Per-request access logging at INFO with method, path, status, duration.

### CLI

- `juno start [--config PATH] [--host H] [--port P]`
- `juno init-config` — writes the default config without starting.
- Also runs as `python -m server start ...`.
- Bad config → exit code 2 with a plain-text error on stderr. No traceback.

### Test client (`client.py`)

```bash
python client.py "Hey Juno, what is 2 + 2?"
```

Connects to the WebSocket, prints chunks as they stream, exits cleanly on
`done`. Purely a Phase 1 smoke-test tool; not the companion app.

---

## Definition of done — verified

- [x] `juno start` boots the server cleanly.
- [x] `GET /api/health` returns 200 with Ollama status.
- [x] `POST /api/chat` returns a structured response or a clean 502 if
      Ollama is down.
- [x] WebSocket streaming actually streams (verified against a stub
      provider in tests + observed via the client).
- [x] Test client works end-to-end.
- [x] Config validation reports bad values clearly (verified manually with
      `port: 99999` → "server.port: Input should be less than or equal to
      65535").
- [x] Ollama unavailable at startup → warning, not crash; reflected in
      `/api/health`.
- [x] All code is typed, with explanatory comments only where the *why* is
      non-obvious.
- [x] `docs/phase1.md` exists.

`pytest -q` → 15 passed, 1 skipped (the live-Ollama integration test;
opt in with `JUNO_TEST_OLLAMA=1` once Ollama is installed).

---

## Notable decisions

1. **httpx, not the `ollama` Python client.** Direct HTTP gives full
   control over the streaming parser and avoids a heavy dependency for
   what amounts to two endpoints.
2. **`extra="forbid"` everywhere on config models.** Typos in YAML keys
   become validation errors instead of "the value silently didn't apply."
3. **Streaming does not retry.** Once any chunk has been forwarded to the
   client, switching providers mid-response would produce a corrupt
   answer. Failures bubble up as a `{"error": ...}` frame.
4. **Reports loaded per-turn, not per-session.** Background-layer outputs
   take effect on the next user message without a server restart, which
   matches the "always-on context" promise from the README.
5. **Session memory in-process only.** Phase 7 owns persistence and
   vector retrieval. Wiring a half-baked persistence layer in now would
   create migration pain.
6. **Reports directory under repo root for now.** Phase 3 will likely
   move it under `~/.juno/` alongside the config so background-layer
   output lives with user state instead of source code. One line to
   change in `server/api/app.py::_default_reports_dir`.

---

## What Phase 2 needs from this

Phase 2 (voice pipeline) extends the Interactive Layer at its API boundary:

- A new endpoint accepts an audio blob, runs STT, calls
  `interactive.handle_text(...)` (or `stream_text`), runs TTS on the
  reply, and returns the audio.
- `InteractiveLayer` itself does not change shape — text in, text out
  remains the canonical interface.
- The wake-word loop and audio capture live in the companion app; the
  server only sees finalized utterances. (Final placement of STT —
  server vs. companion — is open question 3 in CLAUDE.md.)
