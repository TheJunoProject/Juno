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
- `src/plugin-sdk/{bluebubbles,feishu*,googlechat*,matrix*,mattermost*,msteams,nextcloud-talk,nostr,synology-chat,telegram-command*,tlon,twitch,zalo*,irc*,line*}.ts`
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
  across all 89 extensions, Swift module directories, Java package path
  `ai/openclaw/` → `ai/juno/`, scripts, workflows, and the outer project
  directory `openclaw/` → `juno/`).
- All non-binary file contents (TypeScript, Swift, Kotlin, YAML, JSON,
  Markdown, shell, entitlements, Info.plist, etc.).
- Daemon / launchd identifiers: `ai.openclaw.gateway` → `ai.juno.gateway`,
  `ai.openclaw.mac` → `ai.juno.mac`.

### Known side effects

- The repo contains (had) `CLAUDE.md → AGENTS.md` symlinks in many directories.
  BSD `sed -i ''` replaces symlinks with regular files, so those links are now
  regular copies of the post-rename AGENTS.md content. They can be recreated
  with `ln -sf AGENTS.md CLAUDE.md` per-directory if link semantics matter.
- Four binary test fixtures under `juno/test/fixtures/hooks-install/`
  (`tar-reserved-id.tar`, `tar-evil-id.tar`, `tar-hooks.tar`, `zip-hooks.zip`)
  still contain the string `openclaw` inside the archive payloads. These are
  deliberately left untouched: changing bytes inside a tar/zip invalidates the
  archive checksum and breaks the hooks-install test suite. If the fixtures
  eventually need rebuilding, regenerate them with the upstream test harness.

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
- Plus 18 other model-provider extensions (Anthropic, OpenAI, Google, Groq,
  Mistral, etc.) — all kept so users can choose local or API-backed per task

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
- `apps/ios/`, `apps/android/` — companion mobile apps (kept for cross-device
  pairing; can be scaled back later if Juno ends up macOS-only)
- `src/daemon/` — launchd/systemd integration
- `src/pairing/` — device pairing for mobile nodes

### Core agent runtime

- `src/gateway/` — HTTP/WebSocket control plane
- `src/routing/` — session key binding, account routing
- `src/canvas-host/` — Live Canvas rendering (A2UI)
- `src/cron/` — scheduled jobs (Juno's Background Layer hook point)

### Extensions retained (89 total)

Major categories still present in `extensions/`:

- **Model providers** (~25): anthropic, anthropic-vertex, openai, google,
  groq, mistral, moonshot, deepseek, kimi-coding, xai, together, openrouter,
  fireworks, huggingface, nvidia, qianfan, qwen, vllm, sglang, litellm,
  vercel-ai-gateway, cloudflare-ai-gateway, amazon-bedrock,
  amazon-bedrock-mantle, microsoft-foundry, alibaba, arcee, minimax, perplexity,
  stepfun, synthetic, venice, volcengine, xiaomi, zai, chutes, copilot-proxy,
  github-copilot, kilocode, opencode, opencode-go, openshell
- **Memory**: memory-core, memory-lancedb, memory-wiki, active-memory
- **Voice/media**: elevenlabs, deepgram, byteplus, voice-call, speech-core,
  talk-voice, media-understanding-core, image-generation-core,
  video-generation-core, comfy, fal, runway
- **Search/browse**: brave, duckduckgo, exa, firecrawl, searxng, tavily,
  browser
- **System/ops**: codex, device-pair, diagnostics-otel, phone-control,
  webhooks, thread-ownership, diffs, lobster, shared
- **Skill framework**: acpx, llm-task, open-prose, vydra
- **Voyage AI embeddings**: voyage

## Verified / unverified state

**Statically verified (pre-rename pass):**

- Zero orphaned imports of deleted files across `src/`
- Barrel files in `src/config/` no longer reference deleted `types.*.ts`
- No retained extension imports directly from a deleted extension directory
  (the plugin architecture's dynamic discovery made this safe)
- Channel catalog (`src/channels/bundled-channel-catalog-read.ts`) reads from
  `extensions/*/package.json` at build time — will auto-populate an empty
  channel set once `pnpm build` runs

**Not verified (needs a machine with pnpm or bun):**

- `pnpm install` completes against the renamed tree
- `pnpm tsgo:prod` typechecks clean (the `juno/plugin-sdk/*` import surface
  now needs to resolve under the new `juno` scope)
- `pnpm test` passes for remaining suites
- `pnpm build` produces working `dist/`
- Generated artifacts (`src/config/schema.base.generated.ts`,
  `src/config/bundled-channel-config-metadata.generated.ts`,
  `dist/channel-catalog.json`) will be stale until the next build; regenerate
  with the relevant `pnpm config:docs:gen` / `pnpm build` commands
- Swift/Xcode project files and Gradle Android build after module/package
  renames — the bulk replace updated strings but Xcode project schemes and
  Gradle module graphs may need a real build to flush caches

**Tooling not available locally during the strip**: pnpm and bun were not
installed on the machine where the strip was performed (Node 25.9.0 was
present). First action in a verification session:

```bash
# macOS
brew install pnpm
# or
npm install -g pnpm

cd juno
pnpm install
pnpm tsgo:prod
pnpm test
```

## Recommended next steps

1. **Verify the rename compiles** on a machine with pnpm: run
   `pnpm install && pnpm tsgo:prod`. Expect residual errors from generated
   files, `package.json` `name`/`exports` blocks that weren't covered by the
   string replace, or deep test-fixture coupling; triage and patch.
2. **Rebuild native projects** (Swift, Gradle) to flush any cached module
   references the text-replace couldn't update.
3. **Juno-specific build** can start after the base compiles — the
   three-layer architecture (Interactive, Agentic, Background) maps onto the
   retained pieces as follows:
   - Interactive Layer → gateway + companion apps + `realtime-voice` + wake
     word (new)
   - Agentic Layer → `src/agents/` loop + skill execution engine + retained
     provider extensions
   - Background Layer → `src/cron/` + new Juno-owned context-report skills

## Honest risk notes for future-me or another agent

- The upstream codebase has deep boundary rules documented in its
  `CLAUDE.md` / `AGENTS.md` files (kept in place; read them before editing
  `src/channels/`, `src/plugin-sdk/`, or `src/plugins/`). The Phase 2 rename
  rewrote the package name throughout, but the architectural rules those files
  describe still apply to Juno.
- `src/plugins/types.ts` still has JSDoc references to channel names in
  examples — cosmetic, safe to leave.
- Generated config files (`schema.base.generated.ts`,
  `bundled-channel-config-metadata.generated.ts`) still contain channel
  schema from before the strip. They regenerate on build and will naturally
  shrink; if the first typecheck fails because of them, regenerate rather
  than hand-edit.
- `extensions/music-generation-providers.live.test.ts` and
  `extensions/video-generation-providers.live.test.ts` are loose test files at
  the `extensions/` root left over from the upstream layout.
- `package.json` / `pnpm-workspace.yaml` may still reference the old package
  name in fields that aren't simple substrings (e.g. scoped names like
  `@openclaw/*` converted to `@juno/*`, workspace globs). Confirm with
  `pnpm install` before shipping.
