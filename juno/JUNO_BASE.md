# JUNO_BASE

Foundation document for **Juno** — a local, private, Jarvis-style personal AI
assistant forked from [OpenClaw](https://github.com/openclaw/openclaw).

This file records what was kept, what was removed, and the verification state
of the Juno base.

## Fork point

- Upstream: `https://github.com/openclaw/openclaw.git`
- Commit: `eddfffebe8` (April 2026)
- Git history: preserved intact so upstream fixes to retained subsystems
  (skill engine, Ollama integration, voice pipeline) can still be cherry-picked
  via the `upstream` remote.

## Directory layout

```
Juno/
  juno/             <- forked + renamed codebase (originally openclaw/)
  README.md         <- Juno project README
  LICENSE
```

## Phase 1 — Strip-down (done)

### Messaging-platform channels (25 extension directories removed)

Deleted under `extensions/`:

- WhatsApp, Telegram, Discord, Slack, Signal
- iMessage + BlueBubbles (iMessage bridge)
- Matrix, Microsoft Teams, IRC
- Feishu, LINE, Mattermost, Nextcloud Talk, Synology Chat
- Zalo, ZaloUser, QQ Bot, WeChat
- Nostr, Twitch, Google Chat, Tlon
- `qa-channel`, `qa-matrix` (channel QA scaffolding)

### Channel-specific code in `src/` (~90 files)

- `src/config/types.{discord,googlechat,imessage,msteams,slack,telegram,whatsapp,irc,signal}.ts`
- `src/config/zod-schema.providers-whatsapp.ts`
- `src/plugin-sdk/{bluebubbles,feishu*,googlechat*,matrix*,mattermost*,msteams,nextcloud-talk,nostr,telegram-command*,tlon,twitch,zalo*,irc*,line*}.ts`
- `src/channels/plugins/bluebubbles-actions.ts`
- `src/channels/plugins/contracts/plugins-core-extension.{discord,imessage,slack,telegram,whatsapp}.contract.test.ts`
- `src/security/audit-channel-*.test.ts` (Discord, Slack, Telegram, Zalo, Synology, Feishu)
- `src/secrets/runtime-{discord,telegram,matrix,nextcloud-talk,zalo}*.ts`
- `src/cli/program/message/register.discord-admin.ts`
- `src/commands/channels.*-{telegram,signal,mattermost}*.test.ts`
- `src/agents/pi-tools.whatsapp-login-gating.test.ts`
- `src/plugins/runtime-plugin-boundary.whatsapp.test.ts`
- `src/gateway/server.startup-matrix-migration.integration.test.ts`
- `src/commands/onboard-channels.e2e.test.ts`
- `src/channels/plugins/contracts/channel-import-guardrails.test.ts`
- `src/plugins/contracts/plugin-sdk-runtime-api-guardrails.test.ts`

### Channel docs

All 23 platform-specific files under `docs/channels/` (whatsapp.md,
telegram.md, discord.md, slack.md, signal.md, imessage.md, bluebubbles.md,
matrix.md, msteams.md, irc.md, feishu.md, line.md, mattermost.md,
nextcloud-talk.md, synology-chat.md, zalo.md, zalouser.md, qqbot.md, wechat.md,
nostr.md, twitch.md, googlechat.md, tlon.md, qa-channel.md).

Generic channel-framework docs were **kept** (they describe the channel
contract and are still useful for Juno's companion-app integration design):
`broadcast-groups.md`, `channel-routing.md`, `group-messages.md`, `groups.md`,
`index.md`, `location.md`, `pairing.md`, `troubleshooting.md`.

### Marketplace reference (infra kept)

- Removed the system-prompt injection pointing agents at the ClawHub
  marketplace URL (`src/agents/system-prompt.ts`)
- Removed the Discord community link and upstream docs mirror from the same
  block
- **Kept** the skill-registry client infrastructure (now at
  `src/infra/junohub.ts`, `src/plugins/junohub.ts`, `skills/junohub/`, gateway
  endpoints `/skills/search` etc.) so Juno's own skill-registry system can be
  built on top of it later without re-implementing plumbing.

### Hub-file patches

- `src/config/types.ts` — removed barrel re-exports for 9 deleted
  `types.*.ts` files (discord, googlechat, imessage, msteams, slack, telegram,
  whatsapp, irc, signal)
- `src/config/channel-capabilities.ts` — replaced
  `SlackCapabilitiesConfig | TelegramCapabilitiesConfig` import with a generic
  `string[] | Record<string, unknown>` type; the logic was already
  channel-agnostic.

### CHANGELOG disclaimer

`CHANGELOG.md` was prepended with a Juno fork header at the top; the full
upstream OpenClaw history below it was left intact (deliberately honest about
what was forked and when). New Juno release entries should be added above the
`---` separator.

## Phase 2 — Rename (done)

Bulk content + filename replacement across the tree:

| From                 | To                 |
|----------------------|--------------------|
| `OpenClaw`           | `Juno`             |
| `openclaw`           | `juno`             |
| `OPENCLAW`           | `JUNO`             |
| `Claw` (Clawdia etc.)| `Juno`             |
| `claw` (clawhub etc.)| `juno`             |
| `CLAW`               | `JUNO`             |
| `Molty`              | `Juno`             |
| `molty`              | `juno`             |

Applied to:

- File and directory names (including `openclaw.plugin.json` → `juno.plugin.json`
  across all remaining extensions, Swift module directories, Java package path
  `ai/openclaw/` → `ai/juno/`, scripts, workflows, and the outer project
  directory `openclaw/` → `juno/`).
- All non-binary file contents (TypeScript, Swift, Kotlin, YAML, JSON,
  Markdown, shell, entitlements, Info.plist, etc.).
- Daemon / launchd identifiers: `ai.openclaw.gateway` → `ai.juno.gateway`,
  `ai.openclaw.mac` → `ai.juno.mac`.

## Phase 3 — Final cleanup (done)

### Cuts

- `Swabble/` — whole Swift wake-word sidecar project removed (not used by Juno).
- `apps/ios/`, `apps/android/` — mobile companion apps removed (Juno targets
  macOS; mobile can be re-introduced later if needed).
- `assets/` — upstream marketing/image assets removed.
- `docs/` — upstream Mintlify docs site removed. **Exception:**
  `docs/reference/templates/` was restored because `src/agents/workspace.ts`
  reads those files at runtime to seed new agent workspaces (AGENTS.md,
  BOOTSTRAP.md, HEARTBEAT.md, IDENTITY.md, SOUL.md, TOOLS.md, USER.md). Juno's
  own docs will be rebuilt around the actual Juno surface separately.
- `extensions/lobster/` + `src/plugin-sdk/lobster.ts` — the upstream "lobster"
  branding/skill extension removed.
- `dream-diary-preview-v2.html`, `dream-diary-preview-v3.html`, `fix2.py` —
  upstream scratch artifacts removed.

### Renames / residuals swept

- `src/cli/junobot-cli.ts` → `src/cli/juno-cli.ts` (filename caught up to the
  Phase 2 content rename).
- Residual `junod`, `junobot`, `junodbot` identifiers replaced with `juno`
  equivalents across non-CHANGELOG files.
- Lobster emoji (🦞) stripped from non-CHANGELOG source/docs/tests. One
  accidental newline-consumption in
  `extensions/qa-lab/web/src/ui-render.ts` was repaired by hand.

### Dependency + sidecar cleanup

- `package.json`: dropped `@whiskeysockets/baileys` (WhatsApp),
  `@matrix-org/matrix-sdk-crypto-nodejs`, `@tloncorp/api`, and
  `@tloncorp/tlon-skill` from `onlyBuiltDependencies`. Removed the entire
  `patchedDependencies` block (the only entry was a baileys patch).
- Deleted `patches/@whiskeysockets__baileys@7.0.0-rc.9.patch`.
- `scripts/lib/bundled-runtime-sidecar-paths.json` trimmed from 38 entries to
  the 12 extensions Juno still ships (acpx, browser, copilot-proxy, diffs,
  google, lmstudio, memory-core, ollama, open-prose, voice-call, webhooks,
  zai).
- `scripts/lib/plugin-sdk-entrypoints.json` — removed 30 stale entrypoints
  pointing at deleted messaging-channel SDK subpaths (bluebubbles, feishu\*,
  googlechat\*, irc\*, line\*, matrix\*, mattermost\*, msteams, nextcloud-talk,
  nostr, telegram-command-config, tlon, twitch, zalo\*, zalouser).
- `tsdown.config.ts` — removed explicit `telegram/audit` and `telegram/token`
  entries that referenced the deleted Telegram extension.

### Typecheck fixes (hub files)

The typecheck lane failed at 31 errors across 8 files until these
re-exports of removed channel modules were cleaned up:

- `src/config/zod-schema.providers.ts` — dropped
  `zod-schema.providers-whatsapp.js` re-export.
- `src/plugin-sdk/channel-config-schema.ts` — rewrote to keep only
  channel-agnostic helpers; removed Discord/GoogleChat/IMessage/MSTeams/
  Signal/Slack/Telegram/WhatsApp channel-config schema re-exports.
- `src/plugin-sdk/command-auth.ts` — dropped
  `buildCommandsPaginationKeyboard` re-export (Telegram UI).
- `src/plugin-sdk/compat.ts` — dropped the bluebubbles/bluebubbles-policy
  trailing block.
- `src/plugin-sdk/config-runtime.ts` — dropped Telegram custom-command helpers
  and Discord/Signal/Slack/Telegram config type re-exports.
- `src/cli/program/register.message.ts` — removed the
  `register.discord-admin.js` import + call.
- `src/infra/outbound/outbound-session.test-helpers.ts` — added an explicit
  `candidate: unknown` annotation on a Slack group-channel lookup callback.

## Verification (passing locally)

On this tree, with pnpm 10.33.0 and Node 25 installed:

```bash
JUNO_LOCAL_CHECK=0 pnpm tsgo:prod   # core + extensions typecheck — green
JUNO_LOCAL_CHECK=0 pnpm build       # full tsdown/rolldown build — green
```

The production build emits `dist/` with plugin-sdk entrypoints, bundled
plugin sidecars, hook metadata, canvas-a2ui bundle, and CLI compat shims.

`pnpm test` was also run. Core agent, gateway, and infra suites pass; the
remaining ~120 failing tests are all tests that exercised removed messaging
channels (WhatsApp/Telegram/Discord/Slack/Matrix/etc.) — contract tests that
enumerate the bundled channel catalog, parameterized delivery/routing tests
keyed on deleted channel IDs, and channel-specific guardrail tests. The
functionality they assert over was cut by design in Phase 1. These tests
should be pruned or rewritten alongside the next pass of Juno-specific channel
work rather than individually patched now. The core agent workspace bootstrap
path was the one real regression the test run surfaced; it was fixed by
restoring `docs/reference/templates/` (see Cuts below).

Still open from the reference-doc checklist:

- `pnpm juno setup`, `pnpm gateway:watch`, Ollama round-trip, basic agent
  session, macOS app build, skill execution engine — runtime smoke tests still
  need to be exercised on hardware.

## What was kept (the Juno foundation)

### Skill execution engine

- `src/agents/` — agent loop, tool/skill dispatch, provider streaming,
  subagents, session state
- `src/agents/pi-tools.ts` — tool definitions
- `src/flows/` — agent branching/control flow
- `src/chat/` — message handling, draft streams
- `src/plugins/` — plugin discovery, manifest loading, registry, contract
  enforcement (now without messaging-channel plugins)

### Local model integration

- `extensions/ollama/` — Ollama provider
- `extensions/lmstudio/` — LMStudio provider
- Plus the other model-provider extensions (Anthropic, OpenAI, Google, Groq,
  Mistral, etc.) — all kept so users can choose local or API-backed per task.

### Session and memory management

- `src/sessions/` — session lifecycle, archival, compaction
- `src/context-engine/` — context retrieval for agent prompts
- `extensions/memory-core/`, `memory-lancedb/`, `memory-wiki/` — memory
  backends
- `extensions/active-memory/` — always-on working memory

### Voice and audio pipeline

- `src/realtime-voice/`, `src/realtime-transcription/`, `src/tts/`
- `src/media-understanding/` — audio/image/video understanding
- `extensions/elevenlabs/`, `extensions/deepgram/` — TTS/STT providers
- `extensions/voice-call/` — voice channel (kept; not a messaging channel)
- `extensions/speech-core/`, `extensions/talk-voice/`

### macOS companion app + node hooks

- `apps/macos/` — SwiftUI app (menu bar, Canvas surface, voice wake)
- `src/daemon/` — launchd/systemd integration
- `src/pairing/` — device pairing for future mobile/companion nodes

### Core agent runtime

- `src/gateway/` — HTTP/WebSocket control plane
- `src/routing/` — session key binding, account routing
- `src/canvas-host/` — Live Canvas rendering (A2UI)
- `src/cron/` — scheduled jobs (Juno's Background Layer hook point)

## Next steps

1. Run the runtime smoke tests from the reference doc:
   - `pnpm juno setup`
   - `pnpm gateway:watch` + a basic agent session against Ollama
   - macOS app build + launch
   - one skill roundtrip through the execution engine
2. Begin Juno-specific build on top of the verified base. Mapping to the
   three-layer architecture:
   - Interactive Layer → gateway + macOS app + `realtime-voice` + wake word
   - Agentic Layer → `src/agents/` loop + skill engine + retained providers
   - Background Layer → `src/cron/` + new Juno-owned context-report skills

## Honest risk notes for future-me or another agent

- The upstream codebase has deep boundary rules documented in its
  `CLAUDE.md` / `AGENTS.md` files (kept in place; read them before editing
  `src/channels/`, `src/plugin-sdk/`, or `src/plugins/`). The Phase 2 rename
  rewrote the package name throughout, but the architectural rules those files
  describe still apply to Juno.
- Several config/fixture files under `src/` and `extensions/` still mention
  removed channel IDs (discord, telegram, matrix, slack, etc.) in strings,
  tests, and JSON baselines. These did not block `pnpm tsgo:prod` or
  `pnpm build`, but may surface during `pnpm test` or at runtime when
  registries iterate known IDs. Clean them up as they come up rather than in
  a big sweep.
- Four binary test fixtures under `juno/test/fixtures/hooks-install/`
  still contain the string `openclaw` inside the archive payloads. These are
  deliberately left untouched: changing bytes inside a tar/zip invalidates the
  archive checksum and breaks the hooks-install test suite.
- Generated config files (`schema.base.generated.ts`,
  `bundled-channel-config-metadata.generated.ts`) regenerate on build; if the
  first typecheck of a future session fails because of them, regenerate with
  `pnpm config:docs:gen` rather than hand-edit.
- `extensions/music-generation-providers.live.test.ts` and
  `extensions/video-generation-providers.live.test.ts` are loose test files at
  the `extensions/` root left over from the upstream layout.
