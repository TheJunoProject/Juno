# JUNO_BASE

Foundation document for Juno — a local, private, Jarvis-style personal AI
assistant forked from [OpenClaw](https://github.com/openclaw/openclaw).

This file records what was kept, what was removed, what is still internally
branded "openclaw", and the residual tasks needed to produce a fully clean
Juno base.

## Status: Interim strip-down (Phase 1 of 2)

Phase 1 (this commit) is a **functional strip-down only**: messaging-platform
channels and the ClawHub registry reference have been removed, but the project
still lives in a directory called `openclaw/` and uses `openclaw` internally
(package name, CLI binary, daemon IDs, import paths, Swift module, bundle IDs,
etc.).

Phase 2 — the full rename from OpenClaw/Molty/Claw to Juno — is deferred to a
separate focused session because it touches ~7,300 files and a naive bulk
replacement risks breaking import paths, Swift/Gradle module wiring, and
launchd/systemd identifiers.

## Fork point

- Upstream: `https://github.com/openclaw/openclaw.git`
- Commit: `eddfffebe8` (April 2026)
- Git history: preserved intact so upstream fixes to retained subsystems
  (skill engine, Ollama integration, voice pipeline) can still be cherry-picked.

## Directory layout

```
Juno/
  openclaw/         <- cloned + stripped OpenClaw (will be renamed in Phase 2)
  README.md         <- Juno project README
  LICENSE
```

## What was removed

### Messaging-platform channels (25 extension directories)

Deleted under `extensions/`:

- WhatsApp, Telegram, Discord, Slack, Signal
- iMessage + BlueBubbles (iMessage bridge)
- Matrix, Microsoft Teams, IRC
- Feishu, LINE, Mattermost, Nextcloud Talk, Synology Chat
- Zalo, ZaloUser, QQ Bot, WeChat
- Nostr, Twitch, Google Chat, Tlon
- `qa-channel`, `qa-matrix` (channel QA scaffolding)

### Channel-specific code in `src/`

Approximately 90 files, including:

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

### ClawHub marketplace reference (infra kept)

- Removed the system-prompt injection pointing agents at `https://clawhub.ai`
  (`src/agents/system-prompt.ts`)
- Removed the Discord community link and docs mirror from the same block
- **Kept** the ClawHub client infrastructure (`src/infra/clawhub.ts`,
  `src/plugins/clawhub.ts`, `skills/clawhub/`, gateway endpoints
  `/skills/search` etc.) so Juno's own skill-registry system can be built on
  top of it later without re-implementing plumbing.

### Hub-file patches

- `src/config/types.ts` — removed barrel re-exports for 9 deleted
  `types.*.ts` files (discord, googlechat, imessage, msteams, slack, telegram,
  whatsapp, irc, signal)
- `src/config/channel-capabilities.ts` — replaced
  `SlackCapabilitiesConfig | TelegramCapabilitiesConfig` import with a generic
  `string[] | Record<string, unknown>` type; the logic was already channel-agnostic.

### CHANGELOG disclaimer

`CHANGELOG.md` was prepended with a Juno fork header at the top; the full
OpenClaw history below it was left intact (deliberately honest about what was
forked and when). New Juno release entries should be added above the
`---` separator.

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
  pairing; can be scaled back in Phase 2 if Juno is macOS-only)
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

## What is still internally branded "openclaw" (Phase 2 work)

All of these remain on the to-do list:

1. **Filesystem + package**:
   - Project directory `openclaw/` → rename to `juno/`
   - `package.json` name `openclaw` → `juno`
   - Binary name: `openclaw` CLI → `juno`
   - User data root: `~/.openclaw/` → `~/.juno/`
   - All `openclaw.plugin.json` files in `extensions/` (80+) → `juno.plugin.json`
   - Manifest fields: `openclaw.channel.*`, `openclaw.install.*` → `juno.*`

2. **Public SDK import paths**:
   - `openclaw/plugin-sdk/*` → `juno/plugin-sdk/*`
   - This affects every extension's imports + `package.json` exports block

3. **Daemon / service identifiers**:
   - `ai.openclaw.gateway` → `ai.juno.gateway` (launchd)
   - `ai.openclaw.mac` → `ai.juno.mac`
   - Any systemd unit names

4. **Mobile apps**:
   - macOS: `apps/macos/Sources/OpenClaw/` module rename, `Info.plist`
     CFBundleIdentifier, Sparkle appcast URLs
   - iOS: `apps/ios/` bundle IDs, entitlements, fastlane metadata
   - Android: `apps/android/` applicationId in `build.gradle.kts`, manifest

5. **Swabble**: Swift package in `Swabble/` — untouched in Phase 1; may be
   Juno-renamed or removed depending on role (investigate in Phase 2)

6. **Docs**: `docs/` content, README.md, CONTRIBUTING.md, VISION.md,
   AGENTS.md, docs.acp.md, install scripts in sibling `openclaw.ai` repo

7. **"Molty" / "Claw" nicknames**: not yet audited — Phase 2 should grep
   both case-sensitively and case-insensitively

## Verified / unverified state

**Statically verified (this session):**

- Zero orphaned imports of deleted files across `src/`
- Barrel files in `src/config/` no longer reference deleted `types.*.ts`
- No extension in `src/` imports directly from the deleted extension
  directories (the plugin architecture's dynamic discovery made this safe)
- Channel catalog (`src/channels/bundled-channel-catalog-read.ts`) reads from
  `extensions/*/package.json` at build time — will auto-populate an empty
  channel set once `pnpm build` runs

**Not verified (needs a machine with pnpm or bun):**

- `pnpm install` completes
- `pnpm tsgo:prod` typechecks clean
- `pnpm test` passes for remaining suites
- `pnpm build` produces working `dist/`
- Generated artifacts (`src/config/schema.base.generated.ts`,
  `src/config/bundled-channel-config-metadata.generated.ts`,
  `dist/channel-catalog.json`) will be stale until the next build; regenerate
  with the relevant `pnpm config:docs:gen` / `pnpm build` commands

**Tooling not available locally during Phase 1**: pnpm and bun were not
installed on the machine where the strip was performed (Node 25.9.0 was
present). First action in Phase 2 or a verification session:

```bash
# macOS
brew install pnpm
# or
npm install -g pnpm

cd openclaw
pnpm install
pnpm tsgo:prod
pnpm test
```

## Recommended next steps

1. **Verify Phase 1 compiles** on a machine with pnpm: run `pnpm install &&
   pnpm tsgo:prod`. Expect possible residual errors from generated files or
   deep test-fixture coupling; triage and patch.
2. **Then Phase 2 rename**, tackled in a focused session with a clear
   sequence:
   1. package.json name + workspace updates
   2. SDK import paths (`openclaw/plugin-sdk/*` → `juno/plugin-sdk/*`)
      across extensions, using the package name as the forcing function
   3. Plugin manifest files (`openclaw.plugin.json` → `juno.plugin.json`)
   4. Daemon / bundle IDs (Swift, Gradle, plist, launchd)
   5. User data path root (`~/.openclaw/` → `~/.juno/`)
   6. CLI binary name
   7. Docs + README content
   8. "Molty" / "Claw" audit
3. **Juno-specific build** can start after the stripped base compiles — the
   three-layer architecture (Interactive, Agentic, Background) maps onto the
   retained OpenClaw pieces as follows:
   - Interactive Layer → gateway + companion apps + `realtime-voice` + wake
     word (new)
   - Agentic Layer → `src/agents/` loop + skill execution engine + retained
     provider extensions
   - Background Layer → `src/cron/` + new Juno-owned context-report skills

## Honest risk notes for future-me or another agent

- The OpenClaw codebase has deep boundary rules documented in its
  `CLAUDE.md` / `AGENTS.md` files (kept in place; read them before editing
  `src/channels/`, `src/plugin-sdk/`, or `src/plugins/`). A Phase 2 rename
  can safely rewrite the package name throughout, but the architectural
  rules those files describe still apply to Juno.
- `src/plugins/types.ts` lines 1653, 1655, 1711 reference channel names in
  JSDoc examples only — cosmetic, safe to leave until rename.
- Generated config files (`schema.base.generated.ts`,
  `bundled-channel-config-metadata.generated.ts`) still contain channel
  schema from before the strip. They regenerate on build and will naturally
  shrink; if the first typecheck fails because of them, regenerate rather
  than hand-edit.
- `extensions/music-generation-providers.live.test.ts` and
  `extensions/video-generation-providers.live.test.ts` are loose test files at
  the extension root — they are not extensions themselves. Leave them alone.
