# Phase 5 — System integration (cross-platform backends)

Status: complete (2026-05-06).

Phase 5 makes Juno actually live in the user's life: it can read
their inbox and reply, see their calendar and add events, scan recent
messages, and control their Mac. **Crucially, it does this through a
backend abstraction — Apple Mail / Apple Calendar / Apple Messages /
macOS are *one* set of backends, but the same skills work against
IMAP / SMTP / CalDAV** so users on any OS or any provider can use
the same agent against the same skill surface.

The Phase 3 stub jobs for `email-digest.md`, `calendar.md`, and
`messages.md` are gone — those reports now contain real summaries
written by the same backends the skills use.

Verified live: server boots cleanly with all 8 skills registered and
all 4 integration domains reporting their selected backends. Health
endpoint exposes the full backend matrix (selected + available per
backend). Switching the email backend from `apple_mail` to `imap`
in the config flips the active backend on the next restart with no
code changes.

---

## What was built

### `server/integrations/` — backend abstraction layer

```
server/integrations/
  router.py                 IntegrationsRouter — picks the active backend
  _macos.py                 shared AppleScript runner + safe `quote()`
  email/
    base.py                 EmailBackend ABC + EmailMessage envelope
    apple_mail.py           AppleScript -> Mail.app (no creds, no setup)
    imap.py                 stdlib imaplib + smtplib + email
                            (works with Gmail, iCloud Mail, Outlook,
                             Fastmail, Posteo, ProtonMail Bridge,
                             self-hosted Dovecot, ...)
  calendar/
    base.py                 CalendarBackend ABC + CalendarEvent envelope
    apple_calendar.py       AppleScript -> Calendar.app
    caldav.py               RFC 4791 via optional [calendar] extra
                            (iCloud, Google Calendar via CalDAV bridge,
                             Fastmail, Posteo, Nextcloud, Radicale, ...)
  messages/
    base.py                 MessagesBackend ABC + Message envelope
    apple_messages.py       chat.db read + AppleScript send
                            (per CLAUDE.md hard rule, no third-party
                             messaging integrations — but the abstraction
                             reserves a clean slot for signal-cli /
                             a Linux iMessage proxy in the future)
  system/
    base.py                 SystemBackend ABC
    macos.py                AppleScript + screencapture
                            (Linux backend reserved for Phase 6+
                             companion: xdotool / wmctrl / pactl / grim)
```

Same pattern as `InferenceRouter` and `VoiceRouter`: every known
backend constructed up front (cheap; backends do no IO in
`__init__`); the active one selected per domain via config; skills
and jobs talk only to the router via `context.integrations.<domain>`.

### Cross-platform email — the IMAP backend

`ImapEmailBackend` is pure stdlib (`imaplib`, `smtplib`, `email`) —
no extra deps, works against every IMAP-speaking server in
existence. Highlights:

- Reads `IMAP UNSEEN` from the configured mailbox (`INBOX` by
  default), pulls Subject / From / Date / Message-ID headers only
  (no body — keeps tokens cheap; fetch body via a future skill).
- Decodes RFC 2047 encoded-word headers (`=?utf-8?b?...?=`) so
  Unicode subjects render as text the model can quote.
- SMTP send via `STARTTLS` (port 587) by default; flip
  `use_ssl: true` for implicit TLS (port 465).
- Auth failures translate to `EmailPermissionError` so the skill
  surfaces "go fix your password" instead of a generic SMTP error.
- All blocking IMAP/SMTP calls run on a worker thread
  (`asyncio.to_thread`) so the FastAPI event loop never stalls
  during a slow connect.

Credentials come from env vars in Phase 5
(`password_env: JUNO_IMAP_PASSWORD`). macOS Keychain support is
deferred to Phase 6 — the same config field will accept a
`password_keychain: <account>` form then.

### Cross-platform calendar — the CalDAV backend

`CalDAVCalendarBackend` uses the `caldav` package (optional
`[calendar]` extra). Works against:

- iCloud Calendar (`https://caldav.icloud.com/`)
- Google Calendar (via the CalDAV bridge URL)
- Fastmail, Posteo, Tutanota Bridge
- Self-hosted Nextcloud, Radicale, Baikal, SOGo

Listing, expanding recurring events, and creating events all work
through the same `CalendarBackend` interface as `AppleCalendarBackend`.
iCal generation for new events is a hand-built minimal VEVENT (no
extra dep on `vobject`) since CalDAV servers only validate the
fields we use.

When `caldav` isn't installed, `is_available()` returns `False` and
calls raise a clear "install the extra" error — same graceful
degradation pattern as the optional voice providers.

### Default config additions

```yaml
integrations:
  email:
    backend: apple_mail   # or imap
    imap:
      host: ""
      port: 993
      username: ""
      password_env: JUNO_IMAP_PASSWORD
      use_ssl: true
      mailbox: INBOX
    smtp:
      host: ""
      port: 587
      username: ""
      password_env: JUNO_SMTP_PASSWORD
      use_ssl: false
      use_starttls: true
      from_address: ""

  calendar:
    backend: apple_calendar   # or caldav (requires `pip install -e '.[calendar]'`)
    caldav:
      url: ""
      username: ""
      password_env: JUNO_CALDAV_PASSWORD

  messages:
    backend: apple_messages   # only option today

  system:
    backend: macos            # only option today
```

Pydantic validation rejects unknown backend ids at config load,
so a typo (`backend: apl_mail`) fails fast with a clear error
message instead of crashing on the first skill call.

### Skills updated to route through the router

All four Phase-5 skills now call `context.integrations.<domain>` —
no AppleScript imports anywhere outside the integration package. The
skill layer is now genuinely cross-platform; the only macOS-specific
code lives in the `apple_*.py` backends.

Skill output now includes a `backend` field so the agent can
explain to the user which backend produced a result (e.g.
"checked your inbox via IMAP and found 3 unread"). The Interactive
Layer's just-in-time report loading picks up `email-digest.md`
unchanged — only the *contents* of the report change based on which
backend produced it.

### Background jobs replaced

The Phase 3 stubs at `email_stub.py` / `calendar_stub.py` /
`messages_stub.py` are gone, replaced by `email.py` / `calendar.py`
/ `messages.py`. Each:

- Calls through `context.integrations.<domain>` (same backend the
  skill uses).
- Renders raw structured items the Interactive Layer can quote
  from — no LLM summarisation per cycle (cheap; the model
  paraphrases when the user asks).
- Writes `_Source: Apple Mail.app` (or `IMAP / SMTP`, `CalDAV`,
  `Apple Calendar.app`, ...) into the report so the user sees
  which backend produced it.
- Falls back to a clearly-marked `## Status\n_Permission required..._`
  report on backend errors instead of crashing the runtime.

### `/api/health` integrations matrix

```json
{
  "integrations": {
    "email":    { "apple_mail": {"selected": true, "available": true},
                  "imap":       {"selected": false, "available": false} },
    "calendar": { "apple_calendar": {"selected": true, "available": true},
                  "caldav":         {"selected": false, "available": false} },
    "messages": { "apple_messages": {"selected": true, "available": true} },
    "system":   { "macos":          {"selected": true, "available": true} }
  }
}
```

`is_available()` is a config check (do we have host + creds /
extra installed?), not a real network probe — the operator can see
the layout without paying a CalDAV round-trip on every health
check.

---

## Definition of done — verified

- [x] Same skill code drives Apple Mail OR IMAP based on one
      config field. Verified by flipping `integrations.email.backend`
      and watching the startup log + health endpoint switch.
- [x] CalDAV path imports cleanly with the `[calendar]` extra
      installed; raises a clear "install the extra" error otherwise.
- [x] All four Phase-5 background jobs render real-data reports
      (or "permission required" reports) — no Phase 3 placeholders
      left in the codebase or the on-disk reports.
- [x] Tests never invoke real AppleScript / IMAP / CalDAV — all
      backend interaction goes through `_fakes.py` helpers.
- [x] `pytest -q` → **121 passed, 10 skipped**.
- [x] With `JUNO_TEST_OLLAMA=1 JUNO_TEST_MODEL=gemma4:latest` →
      **129 passed, 2 skipped** in 3m05s. The 2 skips are the
      non-Mac clipboard fallback (correctly skipped on macOS) and
      the missing-`caldav`-package error path (correctly skipped
      since we installed the extra).
- [x] Adding a new backend is one new file under
      `server/integrations/<domain>/<name>.py` plus one Literal
      entry in `server/config/schema.py` plus one router-
      registration line in `server/integrations/router.py`. No
      changes anywhere else.

---

## Notable decisions

1. **Stdlib-only IMAP/SMTP.** `imaplib`, `smtplib`, and `email` are
   all in the Python standard library. No `imapclient` /
   `aiosmtplib` dep. The blocking calls run on `asyncio.to_thread`
   so the loop stays responsive.
2. **`caldav` is an optional extra.** The default backend is Apple
   Calendar (zero deps); CalDAV is for users on Linux / Windows /
   non-Apple ecosystems. Hiding it behind `[calendar]` keeps the
   base install lean.
3. **Hand-built VEVENT iCal in the CalDAV backend.** The `caldav`
   package re-exports `vobject`, but pulling that in for the four
   fields we actually set (UID, DTSTAMP, DTSTART, DTEND, SUMMARY,
   LOCATION) was overkill. Hand-built strings are 30 lines.
4. **Credentials via env vars only in Phase 5.** macOS Keychain
   integration (via `security` CLI or `keyring`) is deferred to
   Phase 6 — same config field will accept a `password_keychain`
   form then.
5. **`is_available()` is a config check, not a probe.** Real
   network probes on every `/api/health` would be slow + noisy.
   The skill call is the source of truth for "does this actually
   work right now"; health just shows what's wired.
6. **Reports identify their backend.** Every Phase-5 background
   report carries `_Source: <backend.name>_` so the user can
   distinguish "Apple Mail says inbox is clear" from "IMAP says
   inbox is clear" at a glance. Useful when configuring two
   accounts later.
7. **Tests never touch real macOS apps.** A regression in Phase 5
   v0 made the smoke test fire real AppleScript at the dev's
   inbox. The `tests/_fakes.py` helper installs in-memory backends
   that record every call — the only path that reaches AppleScript
   is the live verification recipe in this doc.
8. **Schema-level backend ids.** Backends are `Literal["apple_mail",
   "imap", ...]` instead of free strings — typos in the config
   become Pydantic validation errors at load, not runtime crashes.

---

## Phase 6 onwards — what's left

The next phase is the **macOS companion app** (SwiftUI). It will:

- Connect to the local server's `/api/chat/stream` and
  `/api/voice/turn/stream`.
- Subscribe to `WS /api/events/stream` for proactive interrupts.
- Render the `intent` / `plan` / `tool_call` / `tool_result` events
  the Phase 4 streaming wire format already emits.
- Run wake-word detection locally (the server only holds the
  config; see Phase 2 docs).

After that, Phase 7 (conversation memory + vector retrieval) and
Phase 8 (optional intent-classifier LoRA) close out the build
order. Email keychain support, Linux backends, and the browser
skill all sit naturally in Phase 6+ work.

---

## How to switch backends

### Use IMAP instead of Apple Mail

```bash
# 1. Get an app password from your provider:
#    Gmail   -> https://myaccount.google.com/apppasswords
#    iCloud  -> https://account.apple.com/account/manage  ("App-Specific Passwords")
#    Fastmail -> https://app.fastmail.com/settings/security/devicepasswords/

export JUNO_IMAP_PASSWORD=xxxx-xxxx-xxxx-xxxx
export JUNO_SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # often the same value

# 2. Edit ~/.juno/config.yaml:
#    integrations:
#      email:
#        backend: imap
#        imap:
#          host: imap.gmail.com         # or imap.mail.me.com / imap.fastmail.com / ...
#          username: you@gmail.com
#        smtp:
#          host: smtp.gmail.com
#          username: you@gmail.com
#          from_address: you@gmail.com

# 3. Restart Juno. Health should show:
#    "imap": { "selected": true, "available": true }
```

### Use CalDAV instead of Apple Calendar

```bash
pip install -e '.[calendar]'
export JUNO_CALDAV_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Edit ~/.juno/config.yaml:
#   integrations:
#     calendar:
#       backend: caldav
#       caldav:
#         url: https://caldav.icloud.com/   # or your CalDAV provider
#         username: you@icloud.com
```
