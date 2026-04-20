---
summary: "Install, configure, and manage Juno plugins"
read_when:
  - Installing or configuring plugins
  - Understanding plugin discovery and load rules
  - Working with Codex/Claude-compatible plugin bundles
title: "Plugins"
sidebarTitle: "Install and Configure"
---

# Plugins

Plugins extend Juno with new capabilities: channels, model providers,
tools, skills, speech, realtime transcription, realtime voice,
media-understanding, image generation, video generation, web fetch, web
search, and more. Some plugins are **core** (shipped with Juno), others
are **external** (published on npm by the community).

## Quick start

<Steps>
  <Step title="See what is loaded">
    ```bash
    juno plugins list
    ```
  </Step>

  <Step title="Install a plugin">
    ```bash
    # From npm
    juno plugins install @juno/voice-call

    # From a local directory or archive
    juno plugins install ./my-plugin
    juno plugins install ./my-plugin.tgz
    ```

  </Step>

  <Step title="Restart the Gateway">
    ```bash
    juno gateway restart
    ```

    Then configure under `plugins.entries.\<id\>.config` in your config file.

  </Step>
</Steps>

If you prefer chat-native control, enable `commands.plugins: true` and use:

```text
/plugin install junohub:@juno/voice-call
/plugin show voice-call
/plugin enable voice-call
```

The install path uses the same resolver as the CLI: local path/archive, explicit
`junohub:<pkg>`, or bare package spec (JunoHub first, then npm fallback).

If config is invalid, install normally fails closed and points you at
`juno doctor --fix`. The only recovery exception is a narrow bundled-plugin
reinstall path for plugins that opt into
`juno.install.allowInvalidConfigRecovery`.

## Plugin types

Juno recognizes two plugin formats:

| Format     | How it works                                                       | Examples                                               |
| ---------- | ------------------------------------------------------------------ | ------------------------------------------------------ |
| **Native** | `juno.plugin.json` + runtime module; executes in-process       | Official plugins, community npm packages               |
| **Bundle** | Codex/Claude/Cursor-compatible layout; mapped to Juno features | `.codex-plugin/`, `.claude-plugin/`, `.cursor-plugin/` |

Both show up under `juno plugins list`. See [Plugin Bundles](/plugins/bundles) for bundle details.

If you are writing a native plugin, start with [Building Plugins](/plugins/building-plugins)
and the [Plugin SDK Overview](/plugins/sdk-overview).

## Official plugins

### Installable (npm)

| Plugin          | Package                | Docs                                 |
| --------------- | ---------------------- | ------------------------------------ |
| Matrix          | `@juno/matrix`     | [Matrix](/channels/matrix)           |
| Microsoft Teams | `@juno/msteams`    | [Microsoft Teams](/channels/msteams) |
| Nostr           | `@juno/nostr`      | [Nostr](/channels/nostr)             |
| Voice Call      | `@juno/voice-call` | [Voice Call](/plugins/voice-call)    |
| Zalo            | `@juno/zalo`       | [Zalo](/channels/zalo)               |
| Zalo Personal   | `@juno/zalouser`   | [Zalo Personal](/plugins/zalouser)   |

### Core (shipped with Juno)

<AccordionGroup>
  <Accordion title="Model providers (enabled by default)">
    `anthropic`, `byteplus`, `cloudflare-ai-gateway`, `github-copilot`, `google`,
    `huggingface`, `kilocode`, `kimi-coding`, `minimax`, `mistral`, `qwen`,
    `moonshot`, `nvidia`, `openai`, `opencode`, `opencode-go`, `openrouter`,
    `qianfan`, `synthetic`, `together`, `venice`,
    `vercel-ai-gateway`, `volcengine`, `xiaomi`, `zai`
  </Accordion>

  <Accordion title="Memory plugins">
    - `memory-core` — bundled memory search (default via `plugins.slots.memory`)
    - `memory-lancedb` — install-on-demand long-term memory with auto-recall/capture (set `plugins.slots.memory = "memory-lancedb"`)
  </Accordion>

  <Accordion title="Speech providers (enabled by default)">
    `elevenlabs`, `microsoft`
  </Accordion>

  <Accordion title="Other">
    - `browser` — bundled browser plugin for the browser tool, `juno browser` CLI, `browser.request` gateway method, browser runtime, and default browser control service (enabled by default; disable before replacing it)
    - `copilot-proxy` — VS Code Copilot Proxy bridge (disabled by default)
  </Accordion>
</AccordionGroup>

Looking for third-party plugins? See [Community Plugins](/plugins/community).

## Configuration

```json5
{
  plugins: {
    enabled: true,
    allow: ["voice-call"],
    deny: ["untrusted-plugin"],
    load: { paths: ["~/Projects/oss/voice-call-extension"] },
    entries: {
      "voice-call": { enabled: true, config: { provider: "twilio" } },
    },
  },
}
```

| Field            | Description                                               |
| ---------------- | --------------------------------------------------------- |
| `enabled`        | Master toggle (default: `true`)                           |
| `allow`          | Plugin allowlist (optional)                               |
| `deny`           | Plugin denylist (optional; deny wins)                     |
| `load.paths`     | Extra plugin files/directories                            |
| `slots`          | Exclusive slot selectors (e.g. `memory`, `contextEngine`) |
| `entries.\<id\>` | Per-plugin toggles + config                               |

Config changes **require a gateway restart**. If the Gateway is running with config
watch + in-process restart enabled (the default `juno gateway` path), that
restart is usually performed automatically a moment after the config write lands.

<Accordion title="Plugin states: disabled vs missing vs invalid">
  - **Disabled**: plugin exists but enablement rules turned it off. Config is preserved.
  - **Missing**: config references a plugin id that discovery did not find.
  - **Invalid**: plugin exists but its config does not match the declared schema.
</Accordion>

## Discovery and precedence

Juno scans for plugins in this order (first match wins):

<Steps>
  <Step title="Config paths">
    `plugins.load.paths` — explicit file or directory paths.
  </Step>

  <Step title="Workspace extensions">
    `\<workspace\>/.juno/<plugin-root>/*.ts` and `\<workspace\>/.juno/<plugin-root>/*/index.ts`.
  </Step>

  <Step title="Global extensions">
    `~/.juno/<plugin-root>/*.ts` and `~/.juno/<plugin-root>/*/index.ts`.
  </Step>

  <Step title="Bundled plugins">
    Shipped with Juno. Many are enabled by default (model providers, speech).
    Others require explicit enablement.
  </Step>
</Steps>

### Enablement rules

- `plugins.enabled: false` disables all plugins
- `plugins.deny` always wins over allow
- `plugins.entries.\<id\>.enabled: false` disables that plugin
- Workspace-origin plugins are **disabled by default** (must be explicitly enabled)
- Bundled plugins follow the built-in default-on set unless overridden
- Exclusive slots can force-enable the selected plugin for that slot

## Plugin slots (exclusive categories)

Some categories are exclusive (only one active at a time):

```json5
{
  plugins: {
    slots: {
      memory: "memory-core", // or "none" to disable
      contextEngine: "legacy", // or a plugin id
    },
  },
}
```

| Slot            | What it controls      | Default             |
| --------------- | --------------------- | ------------------- |
| `memory`        | Active memory plugin  | `memory-core`       |
| `contextEngine` | Active context engine | `legacy` (built-in) |

## CLI reference

```bash
juno plugins list                       # compact inventory
juno plugins list --enabled            # only loaded plugins
juno plugins list --verbose            # per-plugin detail lines
juno plugins list --json               # machine-readable inventory
juno plugins inspect <id>              # deep detail
juno plugins inspect <id> --json       # machine-readable
juno plugins inspect --all             # fleet-wide table
juno plugins info <id>                 # inspect alias
juno plugins doctor                    # diagnostics

juno plugins install <package>         # install (JunoHub first, then npm)
juno plugins install junohub:<pkg>     # install from JunoHub only
juno plugins install <spec> --force    # overwrite existing install
juno plugins install <path>            # install from local path
juno plugins install -l <path>         # link (no copy) for dev
juno plugins install <plugin> --marketplace <source>
juno plugins install <plugin> --marketplace https://github.com/<owner>/<repo>
juno plugins install <spec> --pin      # record exact resolved npm spec
juno plugins install <spec> --dangerously-force-unsafe-install
juno plugins update <id>             # update one plugin
juno plugins update <id> --dangerously-force-unsafe-install
juno plugins update --all            # update all
juno plugins uninstall <id>          # remove config/install records
juno plugins uninstall <id> --keep-files
juno plugins marketplace list <source>
juno plugins marketplace list <source> --json

juno plugins enable <id>
juno plugins disable <id>
```

Bundled plugins ship with Juno. Many are enabled by default (for example
bundled model providers, bundled speech providers, and the bundled browser
plugin). Other bundled plugins still need `juno plugins enable <id>`.

`--force` overwrites an existing installed plugin or hook pack in place.
It is not supported with `--link`, which reuses the source path instead of
copying over a managed install target.

`--pin` is npm-only. It is not supported with `--marketplace`, because
marketplace installs persist marketplace source metadata instead of an npm spec.

`--dangerously-force-unsafe-install` is a break-glass override for false
positives from the built-in dangerous-code scanner. It allows plugin installs
and plugin updates to continue past built-in `critical` findings, but it still
does not bypass plugin `before_install` policy blocks or scan-failure blocking.

This CLI flag applies to plugin install/update flows only. Gateway-backed skill
dependency installs use the matching `dangerouslyForceUnsafeInstall` request
override instead, while `juno skills install` remains the separate JunoHub
skill download/install flow.

Compatible bundles participate in the same plugin list/inspect/enable/disable
flow. Current runtime support includes bundle skills, Claude command-skills,
Claude `settings.json` defaults, Claude `.lsp.json` and manifest-declared
`lspServers` defaults, Cursor command-skills, and compatible Codex hook
directories.

`juno plugins inspect <id>` also reports detected bundle capabilities plus
supported or unsupported MCP and LSP server entries for bundle-backed plugins.

Marketplace sources can be a Claude known-marketplace name from
`~/.claude/plugins/known_marketplaces.json`, a local marketplace root or
`marketplace.json` path, a GitHub shorthand like `owner/repo`, a GitHub repo
URL, or a git URL. For remote marketplaces, plugin entries must stay inside the
cloned marketplace repo and use relative path sources only.

See [`juno plugins` CLI reference](/cli/plugins) for full details.

## Plugin API overview

Native plugins export an entry object that exposes `register(api)`. Older
plugins may still use `activate(api)` as a legacy alias, but new plugins should
use `register`.

```typescript
export default definePluginEntry({
  id: "my-plugin",
  name: "My Plugin",
  register(api) {
    api.registerProvider({
      /* ... */
    });
    api.registerTool({
      /* ... */
    });
    api.registerChannel({
      /* ... */
    });
  },
});
```

Juno loads the entry object and calls `register(api)` during plugin
activation. The loader still falls back to `activate(api)` for older plugins,
but bundled plugins and new external plugins should treat `register` as the
public contract.

Common registration methods:

| Method                                  | What it registers           |
| --------------------------------------- | --------------------------- |
| `registerProvider`                      | Model provider (LLM)        |
| `registerChannel`                       | Chat channel                |
| `registerTool`                          | Agent tool                  |
| `registerHook` / `on(...)`              | Lifecycle hooks             |
| `registerSpeechProvider`                | Text-to-speech / STT        |
| `registerRealtimeTranscriptionProvider` | Streaming STT               |
| `registerRealtimeVoiceProvider`         | Duplex realtime voice       |
| `registerMediaUnderstandingProvider`    | Image/audio analysis        |
| `registerImageGenerationProvider`       | Image generation            |
| `registerMusicGenerationProvider`       | Music generation            |
| `registerVideoGenerationProvider`       | Video generation            |
| `registerWebFetchProvider`              | Web fetch / scrape provider |
| `registerWebSearchProvider`             | Web search                  |
| `registerHttpRoute`                     | HTTP endpoint               |
| `registerCommand` / `registerCli`       | CLI commands                |
| `registerContextEngine`                 | Context engine              |
| `registerService`                       | Background service          |

Hook guard behavior for typed lifecycle hooks:

- `before_tool_call`: `{ block: true }` is terminal; lower-priority handlers are skipped.
- `before_tool_call`: `{ block: false }` is a no-op and does not clear an earlier block.
- `before_install`: `{ block: true }` is terminal; lower-priority handlers are skipped.
- `before_install`: `{ block: false }` is a no-op and does not clear an earlier block.
- `message_sending`: `{ cancel: true }` is terminal; lower-priority handlers are skipped.
- `message_sending`: `{ cancel: false }` is a no-op and does not clear an earlier cancel.

For full typed hook behavior, see [SDK Overview](/plugins/sdk-overview#hook-decision-semantics).

## Related

- [Building Plugins](/plugins/building-plugins) — create your own plugin
- [Plugin Bundles](/plugins/bundles) — Codex/Claude/Cursor bundle compatibility
- [Plugin Manifest](/plugins/manifest) — manifest schema
- [Registering Tools](/plugins/building-plugins#registering-agent-tools) — add agent tools in a plugin
- [Plugin Internals](/plugins/architecture) — capability model and load pipeline
- [Community Plugins](/plugins/community) — third-party listings
