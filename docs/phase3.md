# Phase 3 — Background Layer

Status: complete (2026-05-03).

The Background Layer makes Juno feel context-aware. While the user
isn't talking to it, scheduled jobs read external sources (today: RSS
feeds) and write structured markdown reports the Interactive Layer
picks up on the next turn. The user asks "what's in the news?" and
Juno answers from the freshly-summarised brief sitting in
`memory/reports/news.md`.

This phase is the architecture (scheduler, event bus, runtime,
report-write pipeline) plus the first real job (RSS). Email,
calendar, and messages ship as documented stubs that exercise the
pipeline end-to-end and pin the report filenames + schemas the
Phase 5 implementations will follow.

---

## What was built

### Path layout (new)

User state moved off the repo root and onto `~/.juno/`:

```
~/.juno/
  config.yaml              (already there from Phase 1)
  memory/
    reports/               ← Background writes, Interactive reads
    conversations/         ← Phase 7
    knowledge/             ← Phase 7
  voices/                  ← Piper voice models (Phase 2)
  scheduler.db             ← optional, only when persist_jobs=true
```

`server/config/paths.py` resolves all of this from a single
`paths.base` config field (default `~/.juno`, override with any
absolute path). Tests root the layout in tmp_path via
`config.paths.base = str(tmp_path / "juno")`.

### Scheduler (`server/scheduler/`)

- **`JunoScheduler`** wraps APScheduler's `AsyncIOScheduler`. Cron
  triggers, one-off date triggers, manual `run_now`. Runs jobs on the
  FastAPI event loop so jobs share the same `httpx` clients and
  inference router instances as the request path.
- **In-memory jobstore by default.** Phase 3 jobs are all cron
  triggers that get re-registered with `replace_existing=True` on
  every startup, so persistence is a no-op. Persistence is reserved
  for Phase 5+ one-off date jobs (reminders) — when enabled, jobs
  must be reachable via textual reference (`module:function`) since
  APScheduler can't pickle closures.
- **`coalesce=True`** + `misfire_grace_time=300` — long server
  downtime doesn't replay a queue of identical "summarise RSS" jobs.

### Event bus (`server/scheduler/bus.py`)

- `asyncio.Queue`-based pub/sub with topic-keyed fan-out.
- Async-context-managed subscribers — `async with bus.subscribe(t) as
  stream: async for ev in stream: ...`.
- Bounded per-subscriber queues; a slow subscriber drops oldest
  events instead of back-pressuring the publisher.
- The interrupt path documented in CLAUDE.md is now live:

  ```
  Background job → bus.publish("interrupts", {...})
                → /api/events/stream subscriber (the future companion)
                → notification surfaced
  ```

### Background runtime (`server/agents/background/`)

- `BackgroundRuntime` owns job lifecycle: constructs each job with a
  shared `JobContext` (config, reports_dir, inference router, bus),
  registers it with the scheduler at the configured cron, wraps every
  invocation so report write + error handling + last-run bookkeeping
  happen consistently.
- Atomic-ish report writes: `news.md.tmp` → rename to `news.md`, so
  a partial write never leaves a half-readable report for the
  Interactive Layer.
- Job exceptions are recorded as `last_run.success=False` and never
  take down the runtime.

### Jobs

| Job        | Status      | Output            | Schedule (default)  |
| ---------- | ----------- | ----------------- | ------------------- |
| `rss`      | **real**    | `news.md`         | hourly              |
| `email`    | stub (Phase 5) | `email-digest.md` | every 15 min        |
| `calendar` | stub (Phase 5) | `calendar.md`     | every 15 min        |
| `messages` | stub (Phase 5) | `messages.md`     | every 15 min        |

The RSS job:
- Fetches all configured feeds in parallel with `asyncio.gather`.
- Parses each via `feedparser` (in `asyncio.to_thread` — feedparser
  is synchronous CPU-bound).
- Strips HTML tags, decodes entities, collapses whitespace,
  truncates to `max_chars_per_item` (1500 by default).
- When `summarize=true`, posts the items to the inference router with
  `task_type=background_summarization` (per CLAUDE.md, this routes to
  a small local model). Render: a "Summary" prose section followed by
  a "Raw items" list with source links so claims are verifiable.
- A summariser failure falls back to the raw-items list — the report
  is always useful, just less polished.

The stub jobs write a clearly-marked placeholder describing the
schema the Phase 5 implementation will follow. They serve three
purposes: prove the runtime end-to-end, pin the report filenames so
Phase 4 just-in-time loading can target them, and avoid 404s in the
reports directory while the real impls are pending.

### Interactive Layer enhancement: per-turn "now" context

`docs/agent-architecture.md` §6 says current date / time / timezone
is cheap and must be fresh per turn — not a background job. The
Interactive Layer now injects a small `## Current time` block into
every prompt's `<context>` section, alongside the report contents:

```
<context>
## Current time

- date: Sunday, 03 May 2026
- time: 13:55 EDT
- iso: 2026-05-03T13:55:09-04:00

# Current context (auto-generated by background layer)

## news

(news.md contents)
</context>
```

This is what makes "what time is it?" and "what's in the news?" both
work without a tool call.

### Background API

| Endpoint                              | Purpose                                                |
| ------------------------------------- | ------------------------------------------------------ |
| `GET  /api/background/jobs`           | List jobs with schedule, next/last run.                |
| `POST /api/background/jobs/{name}/run`| Trigger a job manually (out of schedule).              |
| `GET  /api/background/reports`        | List context report files (name, size, mtime).         |
| `GET  /api/background/reports/{name}` | Read a report. Path traversal blocked.                 |
| `WS   /api/events/stream`             | Subscribe to the EventBus interrupt topic. Server emits `subscribed` then a stream of `interrupt` frames. |

`/api/health` is unchanged — the Background Layer's state lives at
`/api/background/jobs` because operators want different data
(schedules, last-run success, durations).

---

## Definition of done — verified

- [x] Scheduler boots, registers all 4 jobs, and `next_run` reflects
      the configured cron expressions.
- [x] `POST /api/background/jobs/email/run` writes `email-digest.md`
      in <1ms with a placeholder body.
- [x] `POST /api/background/jobs/rss/run` against the live HN feed
      and gemma4 produces a real summary in 34s. Report includes a
      prose "Summary" + a "Raw items" list with source links.
- [x] `POST /api/chat` after the RSS job picks up `news.md` via the
      Interactive Layer's just-loaded context — the model
      summarised every story from the report (1368 prompt tokens
      observed, including the per-turn "now" context).
- [x] `WS /api/events/stream` accepts subscriptions and delivers
      published interrupts (verified in unit tests).
- [x] Path layout moved to `~/.juno/` (configurable via `paths.base`).
- [x] Phase 1 + 2 surfaces unchanged: 35 + 7 + 23 new = 58 passing
      tests, 7 skipped (live tests gated on `JUNO_TEST_OLLAMA=1`).

`pytest -q` → **58 passed, 7 skipped**.
With `JUNO_TEST_OLLAMA=1 JUNO_TEST_MODEL=gemma4:latest` → all live
chat / voice tests still green.

---

## Notable decisions

1. **APScheduler over rolling our own.** Cron triggers, date
   triggers, persistence, asyncio integration — all in one
   well-maintained dep. Our wrapper hides the surface.
2. **`persist_jobs: false` by default.** Cron jobs get re-registered
   on every startup (with `replace_existing=True`), so persistence is
   a no-op for Phase 3. Turn it on for Phase 5+ one-off reminders —
   at that point those jobs need to be module-level callables, not
   closures, since APScheduler can't pickle a lambda.
3. **Stub jobs ship as proper jobs, not placeholders.** They go
   through the scheduler, write atomic reports, are listable + manually
   triggerable through the API. The only thing "stub" about them is the
   contents of the report. This means the Interactive Layer has the
   full set of report files to load even before Phase 5 ships, and the
   path is exercised end-to-end every 15 minutes.
4. **Per-turn "now" context belongs to the Interactive Layer, not
   a background job.** Caching current time through a periodic
   report would be both stale and wasteful. Cheap context goes
   inline; expensive context (RSS summarisation, email digesting)
   goes through the cache.
5. **RSS summariser failures don't kill the report.** Falls back to
   the raw items list with an inline error note. The user always
   gets something useful.
6. **Atomic report writes.** `news.md.tmp` → rename. The
   Interactive Layer's per-turn report read can never see a partial
   file.
7. **Path traversal blocked at the route + by Starlette URL
   normalisation.** Belt and braces.
8. **Lifecycle ordering matters.** Jobs are registered before the
   scheduler starts so the first `next_run` calculation already sees
   the full set; teardown reverses the order so in-flight jobs finish
   before the inference router closes its httpx clients.

---

## What Phase 4 needs from this

Phase 4 (Agentic Layer + first skills) gets:

- A live `EventBus` it can publish to (e.g., a long-running skill
  emits progress).
- A `BackgroundRuntime.list_reports()` view that the intent
  classifier can use to decide which reports to load just-in-time
  (per `docs/agent-architecture.md` §6.1).
- A scheduler it can register one-off "follow-up" jobs against
  (e.g., a reminder skill schedules a date trigger).

The `task_type=background_summarization` routing path is now
exercised in production (RSS uses it). When Phase 4 adds the intent
classifier, the same routing pattern lets the user point classifier
inference at a smaller / faster model than the conversational one.

---

## How to run / inspect

```bash
juno start                                 # boots with Background Layer on
curl localhost:8000/api/background/jobs    # list jobs + next runs
curl -X POST localhost:8000/api/background/jobs/rss/run    # trigger now
curl localhost:8000/api/background/reports # list reports
curl localhost:8000/api/background/reports/news.md         # read one
```

Disable the layer entirely:

```yaml
background:
  enabled: false
```

Tweak the RSS feeds:

```yaml
background:
  jobs:
    rss:
      feeds:
        - https://your-favourite-feed.example.com/rss
      max_items_per_feed: 10
      summarize: true
```
