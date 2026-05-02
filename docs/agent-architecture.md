# Juno — Agent Architecture & Prompting

This document codifies the design for Juno's three-layer agent system,
the agentic loop the Agentic Layer will run, and the prompt-engineering
conventions every layer follows.

It synthesises 2025–2026 best practice from Anthropic's *Building
effective agents*, *Effective context engineering for AI agents*, the
Claude prompting guide, Claude Code's plan/explore/code/commit pattern,
and contemporary commentary (Simon Willison, Eugene Yan, Hamel Husain,
Letta).

When the docs and the code disagree, the code wins — but if you're
reaching for a design decision that isn't already encoded here, decide
once, write it down, and link the file.

---

## 1. Workflow vs. Agent: the boundary that shapes the system

Anthropic's distinction:

- A **workflow** orchestrates LLM calls along a predefined code path.
  Predictable, cheap, easy to debug. The LLM is a node, not the driver.
- An **agent** loops dynamically: the LLM chooses the next action based
  on observations from the previous one. Flexible, expensive, harder to
  reason about.

> "Start with workflows. Only graduate to agents when dynamic
> decision-making is genuinely required."

Juno's three layers map cleanly onto this:

| Layer       | Pattern                | Why                                             |
| ----------- | ---------------------- | ----------------------------------------------- |
| Interactive | **Workflow** (router)  | Routes each turn to one of two paths and returns. Predictability matters because it's user-facing latency. |
| Agentic     | **Agent** (true loop)  | Multi-step task execution where the next action depends on tool output. The only place dynamic looping is allowed. |
| Background  | **Scheduled workflow** | Cron-driven jobs that read fixed inputs and write fixed outputs. No reasoning loop needed. |

**Hard rule:** dynamic agentic looping happens only in the Agentic
Layer. The Interactive Layer must terminate in a single inference call
(or one dispatch to the Agentic Layer) per user turn. The Background
Layer has no model-driven branching; if a job needs reasoning, the
reasoning happens in a single bounded call.

If you find yourself wanting to "just let the Interactive Layer call a
tool," dispatch to the Agentic Layer instead. The boundary is
load-bearing.

---

## 2. The Interactive Layer (Phase 1, current)

```
input (text, later audio)
  ↓ STT (Phase 2)
  ↓ intent classification (Phase 4)
  ↓
  Path A — direct: build prompt + context, single inference call, return.
  Path B — agentic: package task, dispatch to Agentic Layer, await result,
                    wrap result for the user, return.
  ↓ TTS (Phase 2)
  ↓ output
```

**Phase 1 scope:** Path A only, no STT/TTS, no intent classification.
Everything goes through the direct path.

**Prompt assembly order (cache-friendly):**

```
[ static persona system prompt ]   ← cache prefix
[ <context> dynamic reports </context> ]  ← varies per turn
[ session history, oldest → newest ]
[ new user turn ]
```

When the Anthropic provider lands, place the cache breakpoint at the
end of the static persona prompt. The dynamic context block comes
after the breakpoint — it changes every few minutes when the Background
Layer regenerates reports, so caching it would burn writes.

**Session history:** in-process LRU. Phase 7 replaces this with a
persistent vector-retrieval store; the Interactive Layer interface
(`handle_text`, `stream_text`) does not change.

---

## 3. The Agentic Layer — design (Phase 4)

The Agentic Layer is Juno's only true agent loop. The design is **plan
→ act → observe → reflect → re-plan-or-finish**, lifted directly from
the pattern Anthropic recommends and Claude Code uses.

### 3.1 The loop

```
receive(task, context)
  │
  plan: produce an ordered list of steps + a success criterion
  │
  loop:
  │   choose next step
  │   call tool(s) — parallel where the manifest allows
  │   observe results (truncated as documented in §6)
  │   if success criterion met:        → finish
  │   if step failed N times:          → escalate or fail
  │   if context budget at threshold:  → compact (summarise + reset)
  │   else:                            → reflect, possibly re-plan
  │
  finish: produce a structured result for the Interactive Layer
```

### 3.2 The "done" criterion is mandatory, not optional

Every task dispatched to the Agentic Layer **must arrive with a
machine-checkable success criterion**. The Interactive Layer is
responsible for synthesising one before dispatch. Examples:

- "Summarise email X" → criterion: response contains a non-empty
  summary string conforming to the SummaryResult schema.
- "Find a coffee shop near me open now" → criterion: at least one
  result with name, address, and `open_now: true` against the search
  output schema.
- "Send a message to Alex saying X" → criterion: messaging skill
  returns `{sent: true}` for the resolved contact.

If the Interactive Layer cannot produce a checkable criterion, it asks
the user one clarifying question (per the `<uncertainty>` rule in the
system prompt) instead of dispatching.

This is the single highest-leverage design choice in the loop.
Without it the loop runs forever or stops too early.

### 3.3 Plan, don't just react

A plan step before the first tool call materially improves outcomes
on multi-step tasks. The plan is small (3–6 bullet points), produced
by the same model that will execute, and **revisable** — the loop
explicitly reflects after each step and may rewrite the plan.

Pure plan-then-execute (a static plan handed to a dumb executor) is
obsolete: plans go stale within one or two tool calls when the world
turns out to be different from what the planner imagined.

### 3.4 Sub-agent dispatch

For any branch that would otherwise pollute the parent loop's context
(deep research over many pages, scanning a long inbox), spawn a
sub-agent in a clean context. The sub-agent returns a **summary**, not
the raw exploration. This is how Claude Code keeps long sessions
sharp; it generalises directly.

### 3.5 Parallel vs. sequential tool calls

Independent tool calls run in parallel by default. The skill manifest
declares parallelisability (see §7). When in doubt, run sequentially
— concurrency bugs in tool dispatch are subtle and the latency win
isn't worth correctness risk.

### 3.6 Escalation policy

Two distinct mechanisms, do not confuse them:

- **Routing escalation (primary).** The router classifies the task by
  type and dispatches to the configured provider for that task type.
  Cheap/local for classification, summarisation, intent routing; cloud
  for complex multi-step planning, novel domains, ambiguous reasoning.
  This is the *default* policy, set in `inference.task_routing`.
- **Failure escalation (safety net).** After `escalation_attempts`
  failures from the primary provider on a single request, the router
  falls back to `inference.fallback_provider`. This catches transient
  failures and capability mismatches, not the routine routing decision.

If you find yourself escalating to cloud on every other turn, fix the
routing config — don't burn the safety net.

---

## 4. The Background Layer — design (Phase 3)

Cron-driven workflows that read external sources (email, RSS,
calendar) and write structured markdown into `memory/reports/`.

**Constraints (from CLAUDE.md, restated for emphasis):**

- Local models only. No cloud calls. Ever.
- Bounded compute per job. The Background Layer cannot become a
  resource sink — it shares a machine with the Interactive Layer's
  latency-sensitive work.
- Every job has a fixed input → fixed output schema. No reasoning
  loops; if a job needs reasoning, the reasoning happens in a single
  bounded inference call with a tight system prompt.

**Prompt design.** Background-job prompts are tiny (target < 500
tokens). They run on small models (Phi-4 Mini, Qwen 2.5 1.5B) where
verbose prompts disproportionately degrade output quality. Use the
six-section structure but expect each section to be 1–3 lines.

**Hooks vs. prompts.** Anything that *must* happen on a schedule
belongs in deterministic scheduler code, not in a model prompt. The
prompt advises; the scheduler enforces.

---

## 5. Prompt design — the six-section structure

Every layer's system prompt follows the same skeleton:

```xml
<identity>     Who this layer is. One or two sentences.
<role>         What this layer's job is.
<capabilities> What it can and can't do today. Be honest.
<behavior>     Style, tone, what to do, what never to do.
<response>     Output format guidance. Positive examples.
<uncertainty>  How to handle unknowns and tool failures.
<context>      Slot for dynamic context, injected at request time.
```

Why XML tags rather than markdown headers: tags are Anthropic's
official structuring primitive (Claude attends to them
disambiguatingly), and they don't break when the body contains
markdown.

**Length budget.** The Anthropic guidance is unambiguous: bloated
prompts get partially ignored. Discipline:

| Layer       | Target system-prompt size |
| ----------- | ------------------------- |
| Interactive | ≤ 2,000 tokens            |
| Agentic     | ≤ 3,000 tokens (skill schema dominates; keep narrative tight) |
| Background  | ≤ 500 tokens              |

For every line, ask "would removing this cause a regression?" If not,
cut it.

**Few-shot examples** (3–5, wrapped in `<example>` tags, diverse,
covering edge cases) remain the highest-leverage shaping technique
when output format matters. Save them for prompts where format
correctness is load-bearing — which mainly means the Agentic Layer
and structured background jobs.

---

## 6. Context engineering

Anthropic's framing: context is **finite with diminishing marginal
returns**. The discipline is "the smallest set of high-signal tokens
that maximise the likelihood of the desired outcome."

### 6.1 Just-in-time loading (Phase 4 work)

Phase 1 loads every report in `memory/reports/` into every Interactive
turn. That is fine while there are zero reports, and acceptable while
there are six. It will not scale.

Phase 4 replaces this with intent-aware loading: the intent classifier
emits a tag set, and only reports tagged with one of those tags are
injected. Examples:

| Intent                             | Reports to load           |
| ---------------------------------- | ------------------------- |
| "What's on my calendar today?"     | calendar                  |
| "Did anyone email me about X?"     | email-digest              |
| "Catch me up on the news"          | news, projects            |
| Open-ended chat / no clear intent  | none                      |

### 6.2 Tool result truncation

Long tool outputs (file reads, search dumps, log extracts) are the
primary context killer. Every skill that returns potentially-large
output must:

- Return a head + tail with byte-range metadata.
- Accept an `offset` / `limit` / `range` parameter so the agent can
  request the rest deliberately.

No skill ever pastes a 50k-line log into the conversation.

### 6.3 Compaction

Long Agentic Layer loops will hit a context budget. When that happens,
summarise and reinitialise: the summariser preserves "files modified,
key decisions, outstanding TODOs" (analogous to Claude Code's
auto-compact). Customisable per task type.

### 6.4 Sub-agent dispatch with summary

See §3.4. A sub-agent context is born clean and dies clean — what
returns to the parent is a summary the parent can act on, not the
sub-agent's transcript.

### 6.5 Prompt caching (Anthropic provider, Phase 4+)

Two TTLs: 5 min (default, 1.25× write cost) and 1 hour (2× write
cost). Reads are ~10% of base input cost.

**Place breakpoints on stable prefixes only.** For Juno that means:

```
[ static persona system prompt ]                ← cache_control here
[ <context> dynamic reports </context> ]
[ session history ]
[ new user turn ]
```

Anti-pattern: a breakpoint on anything that contains the user's query,
the time, or a per-turn UUID. That makes every turn a cache miss.

For Background → Interactive flows with > 5 min idle gaps, use the
1h TTL. Multi-turn conversations get auto-caching at the top level.
Maximum 4 explicit breakpoints, 20-block lookback window.

---

## 7. Skill manifest schema (Phase 4)

The CLAUDE.md placeholder schema gets these additions, lifted from the
research consensus on tool design:

```json
{
  "name": "web_search",
  "description": "Search the web and return structured results.",
  "when_to_use": "User asks for a fact you don't reliably know, or for current information.",
  "when_not_to_use": "User asks an opinion, asks about themselves, or the answer is in a context report.",
  "parallelizable": true,
  "input": {
    "query":       { "type": "string", "required": true },
    "max_results": { "type": "number", "required": false, "default": 5 }
  },
  "output": {
    "results": { "type": "array",  "items": { "$ref": "#/definitions/SearchResult" } },
    "summary": { "type": "string" }
  },
  "examples": [
    {
      "input":  { "query": "current Bitcoin price USD" },
      "output": { "summary": "About $68,400 as of 2026-05-02 (CoinGecko).", "results": ["..."] }
    }
  ]
}
```

The `description` and `when_to_use` / `when_not_to_use` strings are
what the model actually reads to decide whether to call. They earn
their tokens. Be specific.

**Native tool calling.** Use the inference provider's native tool-call
API (Ollama exposes one that mirrors OpenAI's; Anthropic, OpenAI, and
Google all do). Parse-from-text patterns are obsolete except for tiny
local models without tool-call support, where JSON mode + schema
validation is the fallback.

---

## 8. Verification — the highest-leverage design choice

> "The single highest-leverage thing you can do is give the agent a
> way to check its own work." — *Claude Code best practices*

For Juno this means:

- The Background Layer's reports are the verification surface for
  proactive claims. Before the Interactive Layer voices "you have
  three urgent emails," it sanity-checks against `email-digest.md`.
- Skills that take action return the post-action state, not just
  `{success: true}`. Sending a message returns the message ID and
  delivery status. Writing a file returns the new file size and
  hash.
- The Agentic Layer's success criterion (§3.2) is the per-task
  verification.

If you can't verify it, don't claim it.

---

## 9. What changes when

| Phase | Adds                                                          |
| ----- | ------------------------------------------------------------- |
| 1     | Interactive Layer Path A. Persona prompt. (Done.)             |
| 2     | STT / TTS at the API boundary. Interactive interface unchanged. |
| 3     | Background Layer + scheduler + first reports.                 |
| 4     | Agentic Layer loop, intent classifier, skill manifest, first skills. Just-in-time report loading. |
| 5     | More skills (system, email, calendar, messages).              |
| 6     | Companion app polish.                                         |
| 7     | Persistent conversation memory + vector retrieval.            |
| 8     | Optional intent-classifier LoRA.                              |

When you build Phase 4, the contract above is what you implement
against. If a real-world constraint forces a deviation, update this
document in the same change set.
