---
summary: "CLI reference for `juno browser` (lifecycle, profiles, tabs, actions, state, and debugging)"
read_when:
  - You use `juno browser` and want examples for common tasks
  - You want to control a browser running on another machine via a node host
  - You want to attach to your local signed-in Chrome via Chrome MCP
title: "browser"
---

# `juno browser`

Manage Juno's browser control surface and run browser actions (lifecycle, profiles, tabs, snapshots, screenshots, navigation, input, state emulation, and debugging).

Related:

- Browser tool + API: [Browser tool](/tools/browser)

## Common flags

- `--url <gatewayWsUrl>`: Gateway WebSocket URL (defaults to config).
- `--token <token>`: Gateway token (if required).
- `--timeout <ms>`: request timeout (ms).
- `--expect-final`: wait for a final Gateway response.
- `--browser-profile <name>`: choose a browser profile (default from config).
- `--json`: machine-readable output (where supported).

## Quick start (local)

```bash
juno browser profiles
juno browser --browser-profile juno start
juno browser --browser-profile juno open https://example.com
juno browser --browser-profile juno snapshot
```

## Quick troubleshooting

If `start` fails with `not reachable after start`, troubleshoot CDP readiness first. If `start` and `tabs` succeed but `open` or `navigate` fails, the browser control plane is healthy and the failure is usually navigation SSRF policy.

Minimal sequence:

```bash
juno browser --browser-profile juno start
juno browser --browser-profile juno tabs
juno browser --browser-profile juno open https://example.com
```

Detailed guidance: [Browser troubleshooting](/tools/browser#cdp-startup-failure-vs-navigation-ssrf-block)

## Lifecycle

```bash
juno browser status
juno browser start
juno browser stop
juno browser --browser-profile juno reset-profile
```

Notes:

- For `attachOnly` and remote CDP profiles, `juno browser stop` closes the
  active control session and clears temporary emulation overrides even when
  Juno did not launch the browser process itself.
- For local managed profiles, `juno browser stop` stops the spawned browser
  process.

## If the command is missing

If `juno browser` is an unknown command, check `plugins.allow` in
`~/.juno/juno.json`.

When `plugins.allow` is present, the bundled browser plugin must be listed
explicitly:

```json5
{
  plugins: {
    allow: ["telegram", "browser"],
  },
}
```

`browser.enabled=true` does not restore the CLI subcommand when the plugin
allowlist excludes `browser`.

Related: [Browser tool](/tools/browser#missing-browser-command-or-tool)

## Profiles

Profiles are named browser routing configs. In practice:

- `juno`: launches or attaches to a dedicated Juno-managed Chrome instance (isolated user data dir).
- `user`: controls your existing signed-in Chrome session via Chrome DevTools MCP.
- custom CDP profiles: point at a local or remote CDP endpoint.

```bash
juno browser profiles
juno browser create-profile --name work --color "#FF5A36"
juno browser create-profile --name chrome-live --driver existing-session
juno browser create-profile --name remote --cdp-url https://browser-host.example.com
juno browser delete-profile --name work
```

Use a specific profile:

```bash
juno browser --browser-profile work tabs
```

## Tabs

```bash
juno browser tabs
juno browser tab new
juno browser tab select 2
juno browser tab close 2
juno browser open https://docs.juno.ai
juno browser focus <targetId>
juno browser close <targetId>
```

## Snapshot / screenshot / actions

Snapshot:

```bash
juno browser snapshot
```

Screenshot:

```bash
juno browser screenshot
juno browser screenshot --full-page
juno browser screenshot --ref e12
```

Notes:

- `--full-page` is for page captures only; it cannot be combined with `--ref`
  or `--element`.
- `existing-session` / `user` profiles support page screenshots and `--ref`
  screenshots from snapshot output, but not CSS `--element` screenshots.

Navigate/click/type (ref-based UI automation):

```bash
juno browser navigate https://example.com
juno browser click <ref>
juno browser type <ref> "hello"
juno browser press Enter
juno browser hover <ref>
juno browser scrollintoview <ref>
juno browser drag <startRef> <endRef>
juno browser select <ref> OptionA OptionB
juno browser fill --fields '[{"ref":"1","value":"Ada"}]'
juno browser wait --text "Done"
juno browser evaluate --fn '(el) => el.textContent' --ref <ref>
```

File + dialog helpers:

```bash
juno browser upload /tmp/juno/uploads/file.pdf --ref <ref>
juno browser waitfordownload
juno browser download <ref> report.pdf
juno browser dialog --accept
```

## State and storage

Viewport + emulation:

```bash
juno browser resize 1280 720
juno browser set viewport 1280 720
juno browser set offline on
juno browser set media dark
juno browser set timezone Europe/London
juno browser set locale en-GB
juno browser set geo 51.5074 -0.1278 --accuracy 25
juno browser set device "iPhone 14"
juno browser set headers '{"x-test":"1"}'
juno browser set credentials myuser mypass
```

Cookies + storage:

```bash
juno browser cookies
juno browser cookies set session abc123 --url https://example.com
juno browser cookies clear
juno browser storage local get
juno browser storage local set token abc123
juno browser storage session clear
```

## Debugging

```bash
juno browser console --level error
juno browser pdf
juno browser responsebody "**/api"
juno browser highlight <ref>
juno browser errors --clear
juno browser requests --filter api
juno browser trace start
juno browser trace stop --out trace.zip
```

## Existing Chrome via MCP

Use the built-in `user` profile, or create your own `existing-session` profile:

```bash
juno browser --browser-profile user tabs
juno browser create-profile --name chrome-live --driver existing-session
juno browser create-profile --name brave-live --driver existing-session --user-data-dir "~/Library/Application Support/BraveSoftware/Brave-Browser"
juno browser --browser-profile chrome-live tabs
```

This path is host-only. For Docker, headless servers, Browserless, or other remote setups, use a CDP profile instead.

Current existing-session limits:

- snapshot-driven actions use refs, not CSS selectors
- `click` is left-click only
- `type` does not support `slowly=true`
- `press` does not support `delayMs`
- `hover`, `scrollintoview`, `drag`, `select`, `fill`, and `evaluate` reject
  per-call timeout overrides
- `select` supports one value only
- `wait --load networkidle` is not supported
- file uploads require `--ref` / `--input-ref`, do not support CSS
  `--element`, and currently support one file at a time
- dialog hooks do not support `--timeout`
- screenshots support page captures and `--ref`, but not CSS `--element`
- `responsebody`, download interception, PDF export, and batch actions still
  require a managed browser or raw CDP profile

## Remote browser control (node host proxy)

If the Gateway runs on a different machine than the browser, run a **node host** on the machine that has Chrome/Brave/Edge/Chromium. The Gateway will proxy browser actions to that node (no separate browser control server required).

Use `gateway.nodes.browser.mode` to control auto-routing and `gateway.nodes.browser.node` to pin a specific node if multiple are connected.

Security + remote setup: [Browser tool](/tools/browser), [Remote access](/gateway/remote), [Tailscale](/gateway/tailscale), [Security](/gateway/security)
