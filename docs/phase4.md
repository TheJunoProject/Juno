# Phase 4 — Agentic Layer + first skills

Status: complete (2026-05-04).

Phase 4 is where Juno gains its capability surface. Until now the
server could chat, generate context reports, and read/write WAV. It
could not *do* anything. With Phase 4 wired up, the model decides
each turn whether the question is conversational (Path A) or wants
tool use (Path B), and on Path B it runs a real plan-act-observe-
reflect loop against a typed skill registry.

Verified end-to-end against `gemma4:latest`: the classifier routes
turns correctly, gemma4 emits structured tool calls via the Ollama
native tool API, the Agentic Layer dispatches to the registered skill,
the skill executes its real backend (DuckDuckGo HTTP, sandboxed file
IO, macOS pbcopy/pbpaste), and the model produces a final user-facing
answer. **94 tests pass against live gemma4 in 2m30s.**

---

## What was built

### Inference layer: native tool calling

`server/inference/base.py` adds `Tool`, `ToolCall`, and tool-related
fields to `Message`, `InferenceRequest`, `InferenceResponse`,
`InferenceChunk`. The Ollama provider now sends `tools=[...]` and
`format="json"` when requested, and parses `message.tool_calls` from
both streaming and non-streaming responses (Ollama only emits tool
calls on the final `done=true` chunk; both paths normalise to the same
`ToolCall` list).

`TaskType` gains `intent_classification`, and `TaskRoutingConfig` gains
the matching `intent_classification` field — operators can route the
classifier to a smaller / faster model than `conversational` if they
have one.

### Skill system

```
server/skills/
  base.py                  Skill, SkillContext, SkillInput/Output, SkillError, SkillResult
  manifest.py              SkillManifest (Pydantic), JSON-schema rendering
  registry.py              SkillRegistry — discovery, registration, tool-list rendering
  _file_sandbox.py         path-allowlist helper used by the file skills

  web_search/              real DuckDuckGo HTML scraper backend
  file_read/               sandboxed UTF-8 read with truncation
  file_write/              atomic write, refuses overwrite by default
  clipboard/               macOS pbcopy / pbpaste
```

Manifests live in `skill.json` next to the implementation and follow
the schema from `docs/agent-architecture.md` §7:

- `name` — must match the class's `name` attribute.
- `description` + `when_to_use` + `when_not_to_use` — what the model
  reads to decide whether to call. The registry composes these into
  the description string sent to the model.
- `parallelizable` — declared per skill; the Agentic Layer dispatches
  parallelisable tool calls in one assistant turn concurrently with
  `asyncio.gather`.
- `input` — accepts both the compact form (`{"x": {"type": "string",
  "required": true}}`) and full JSON Schema. The registry normalises
  to JSON Schema before handing to the model.
- `output`, `examples` — documented; not sent to the model on every
  turn (reserved for prompt-engineering tweaks per the architecture
  doc).

`SkillRegistry.discover()` walks `server/skills/` at startup; every
subdirectory containing a `skill.json` becomes a registered skill.
`as_tools()` renders the registered set into the inference layer's
`Tool` list — one place owns the manifest → tool-definition mapping.

### Agentic Layer

`server/agents/agentic/layer.py` is the plan-act-observe-reflect loop.

```
receive(AgenticTask)
  build messages: [system_prompt, user(instruction + criterion + ctx)]
  loop up to max_iterations:
      response = inference.complete(messages, tools=registry.as_tools())
      messages.append(assistant message with response.tool_calls)
      if no tool_calls:
          emit final → exit
      dispatch tool_calls in parallel via SkillRegistry
      append role=tool messages with results
  if loop ran out: emit error
```

Per `docs/agent-architecture.md` §3:

- **Plan-act-observe-reflect**, not pure ReAct. The first non-empty
  text the model produces gets emitted as a `plan` event for the
  trace.
- **Bounded iterations** (default 6) — the loop can never spin forever.
- **Skill failures don't kill the loop.** A `SkillError` becomes a
  `tool_result` with `ok=false`; the model gets to see the error and
  recover (or surface it cleanly).
- **Parallel tool dispatch** in one assistant turn via
  `asyncio.gather`. The skill manifest's `parallelizable` flag is
  advisory for the model — actual safety lives in the skill code.
- **Streaming surface**: `stream(task)` yields typed `AgenticEvent`
  frames (`plan` / `tool_call` / `tool_result` / `final` / `error`).
  The Interactive Layer forwards these through the WebSocket.

### Intent classifier + Path-A/B routing in the Interactive Layer

`server/agents/interactive/classifier.py` runs on every turn:

- Asks the configured `intent_classification` model for a tight JSON
  decision (`response_format_json=True`).
- Returns a typed `IntentDecision(path, skills, reports, rationale)`.
- Filters the model's skill / report names against the live registry
  + on-disk reports — unknown names get dropped silently so a flaky
  classifier can't dispatch to a non-existent skill.
- Falls back to the safe direct path with no reports if the
  classifier itself fails. Better to give a less-grounded answer
  than crash on every turn.

`InteractiveLayer.stream_turn()` (the new Phase 4 surface) wires it
all together:

1. Run classifier → emit `intent` event.
2. Path A: stream the conversational model's deltas.
3. Path B: dispatch to AgenticLayer; forward `plan` / `tool_call` /
   `tool_result` events; emit the agent's final text as a single
   `delta`; emit `done`.
4. On any failure: emit `error` and stop.

The just-in-time report loading is now real: the system prompt only
contains reports the classifier flagged as relevant. The Phase-3-era
"load everything" pattern is gone. Reports the model didn't ask for
no longer eat context budget.

### Wire format (chat WebSocket)

The streaming `WS /api/chat/stream` endpoint emits a richer set of
frames:

```
{"event": "intent", "path": "direct" | "agentic",
 "skills": [...], "reports": [...], "rationale": str,
 "session_id": str}

{"event": "plan",        "text": str, "session_id": str}              # Path B only
{"event": "tool_call",   "id": str, "name": str, "arguments": {...}}  # Path B only
{"event": "tool_result", "id": str, "name": str,
 "ok": bool, "summary": str, "error": str | null}                     # Path B only

{"delta": str, "session_id": str, ...}    # token chunks (Path A) or final-text (Path B)
{"done": true, "session_id": str}
{"error": str, "detail": str | null}      # on any failure
```

**Backwards compatibility:** Phase 1 clients that ignore unknown keys
keep working. The `delta` and `done` frames have the same shape they
had before. New clients render the trace; old clients see the
conversation.

### API surface

| Endpoint | Purpose |
| --- | --- |
| `GET /api/skills` | List manifests of all registered skills. The companion uses this to render a skill picker / debug pane. |
| `WS /api/chat/stream` | Phase 4 wire format above. Routes through the intent classifier. |
| `POST /api/chat` | Direct path only (kept for the voice turn pipeline; Path B over voice is Phase 5+). |

### Sandboxing

`file_read` / `file_write` resolve every path against an allow-list
that defaults to `<paths.base>/skill-data/` (i.e.
`~/.juno/skill-data/`). Absolute paths outside the allow-list are
rejected; relative paths resolve into the sandbox. Symlink + `..`
escapes are blocked by `Path.resolve()` + a `relative_to` check.

`clipboard` is macOS-only — explicitly rejects with a clean error on
non-Darwin so the model doesn't think it has a tool it doesn't.

`web_search` has a hard cap of 10 results and a 15s timeout. The
DuckDuckGo HTML parser is best-effort: when zero results parse out
(rate limited, layout changed, ...) the skill raises rather than
returning empty so the agent knows to escalate.

---

## Definition of done — verified

- [x] `GET /api/skills` lists the four Phase-4 skills with full
      manifest fields.
- [x] Direct path: `POST /api/chat "who are you?"` against gemma4
      returns the persona answer in 30s with usage tokens.
- [x] Agentic path — file_write: model called the skill with
      `{"path": "test-juno.md", "content": "...", "overwrite": true}`,
      sandbox produced the file at the expected location, and the
      model produced a final confirmation in one assistant turn.
- [x] Agentic path — web_search: real DuckDuckGo result, model
      returned just the title as asked.
- [x] Agentic path — file_read: round-tripped the file the previous
      turn wrote.
- [x] Intent classifier filters unknown skill / report names.
- [x] Skill failures bubble up as `tool_result` with `ok=false` and
      a clean error message; the model recovers.
- [x] Iteration cap fires when the model never produces a final.
- [x] Sandbox rejects `/etc/passwd`, `..`-escapes, and binary file
      reads.

`pytest -q` → **86 passed, 9 skipped** (all 9 are live tests gated
on `JUNO_TEST_OLLAMA=1`).
With `JUNO_TEST_OLLAMA=1 JUNO_TEST_MODEL=gemma4:latest` →
**94 passed, 1 skipped** (the lone skip is the non-Mac clipboard
fallback test, which is correctly skipped on macOS) in 150s.

---

## Notable decisions

1. **Native tool calling, no parse-from-text fallback.** Per
   `docs/agent-architecture.md` §4 the parse-from-text pattern is
   reserved for tiny local models without tool-call support. gemma4
   has it; we use it. A flaky model becomes a model-routing
   problem, not a parser problem.
2. **Skill discovery via filesystem scan.** Every skill is one
   subdirectory + a `skill.json`. No central registry list to keep
   in sync. Adding a new skill is a `mkdir` + two files.
3. **Manifest rendering does the heavy lifting.** The string the
   model sees for each tool is `description + "Use when:" + when_to_use
   + "Do not use when:" + when_not_to_use`. This is the
   highest-leverage prompt text in the system; spending tokens here
   directly improves correct tool selection.
4. **Compact + full-JSON-Schema input forms both accepted.** Skill
   authors don't have to write JSON Schema by hand for trivial cases.
5. **Web search backend is DuckDuckGo HTML.** Fragile by definition,
   but no API key, no rate limit per IP, no extra dep. The `browser`
   skill (CLAUDE.md skill #1, deferred from Phase 4 because of the
   ~150MB Playwright + Chromium download) will eventually replace
   this implementation behind the same `Skill` interface.
6. **Sandbox by default for file IO.** A 1-line config additive in
   Phase 5 will let users open up the allow-list. The default has
   to be safe — agentic file IO is the easiest way to wreck a
   user's home directory.
7. **The WebSocket wire format is additive.** Old `delta`/`done`
   frames keep their Phase 1 shape so Phase-1 / Phase-2 clients
   ignore the new event frames and continue to work. The Phase 6
   companion will render the new ones; Phase 5+ will too.
8. **Voice turn (`POST /api/voice/turn`) deliberately uses the
   non-streaming `handle_text`.** Tool-call streaming through TTS
   is Phase 5+ work — synthesising the agent's intermediate
   "calling tool X..." narration is awkward and not what the user
   wants. Phase 4 keeps voice on Path A.
9. **Iteration cap defaults to 6.** Per the architecture doc, plans
   "go stale within one or two tool calls" — a 6-step cap is plenty
   for any of the four shipped skills and prevents runaway loops.

---

## What Phase 5 needs from this

Phase 5 (macOS system integration: email, calendar, messages, system
controller) gets:

- A typed skill base + registry that Phase 5 implements against. Each
  new skill is one package under `server/skills/` with a manifest +
  class. No agent or router code changes.
- An Agentic Layer that already understands tool failures, parallel
  dispatch, and iteration capping. Real-world skills (email send,
  calendar create-event) just plug in.
- A sandbox model the operator can extend per-skill via config.
- Clear interrupt-channel separation: the Background Layer (Phase 3)
  publishes urgent items via `EventBus`, which the future companion
  subscribes to. Skills can publish there too once they detect
  something the user must see right now.

The intent classifier prompt mentions skills by name; when Phase 5
adds 8 more skills, the classifier prompt grows but the routing logic
doesn't change.

---

## How to drive it

```bash
juno start

# List available skills
curl localhost:8000/api/skills

# Direct path
curl -X POST localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"In one sentence: what are you?"}'

# Agentic path — streamed live in the test client
python client.py "Search the web for 'latest claude release notes' and tell me the top result"
python client.py "Save a file note.md with the line 'phase 4 works'"
python client.py "Read note.md and tell me what it says"
python client.py "Read my clipboard"
```

Sandbox dir: `~/.juno/skill-data/`.
