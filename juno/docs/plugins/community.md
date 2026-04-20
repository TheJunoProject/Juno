---
summary: "Community-maintained Juno plugins: browse, install, and submit your own"
read_when:
  - You want to find third-party Juno plugins
  - You want to publish or list your own plugin
title: "Community Plugins"
---

# Community Plugins

Community plugins are third-party packages that extend Juno with new
channels, tools, providers, or other capabilities. They are built and maintained
by the community, published on [JunoHub](/tools/junohub) or npm, and
installable with a single command.

JunoHub is the canonical discovery surface for community plugins. Do not open
docs-only PRs just to add your plugin here for discoverability; publish it on
JunoHub instead.

```bash
juno plugins install <package-name>
```

Juno checks JunoHub first and falls back to npm automatically.

## Listed plugins

### Codex App Server Bridge

Independent Juno bridge for Codex App Server conversations. Bind a chat to
a Codex thread, talk to it with plain text, and control it with chat-native
commands for resume, planning, review, model selection, compaction, and more.

- **npm:** `juno-codex-app-server`
- **repo:** [github.com/pwrdrvr/juno-codex-app-server](https://github.com/pwrdrvr/juno-codex-app-server)

```bash
juno plugins install juno-codex-app-server
```

### DingTalk

Enterprise robot integration using Stream mode. Supports text, images, and
file messages via any DingTalk client.

- **npm:** `@largezhou/ddingtalk`
- **repo:** [github.com/largezhou/juno-dingtalk](https://github.com/largezhou/juno-dingtalk)

```bash
juno plugins install @largezhou/ddingtalk
```

### Lossless Juno (LCM)

Lossless Context Management plugin for Juno. DAG-based conversation
summarization with incremental compaction — preserves full context fidelity
while reducing token usage.

- **npm:** `@martian-engineering/lossless-juno`
- **repo:** [github.com/Martian-Engineering/lossless-juno](https://github.com/Martian-Engineering/lossless-juno)

```bash
juno plugins install @martian-engineering/lossless-juno
```

### Opik

Official plugin that exports agent traces to Opik. Monitor agent behavior,
cost, tokens, errors, and more.

- **npm:** `@opik/opik-juno`
- **repo:** [github.com/comet-ml/opik-juno](https://github.com/comet-ml/opik-juno)

```bash
juno plugins install @opik/opik-juno
```

### QQbot

Connect Juno to QQ via the QQ Bot API. Supports private chats, group
mentions, channel messages, and rich media including voice, images, videos,
and files.

- **npm:** `@tencent-connect/juno-qqbot`
- **repo:** [github.com/tencent-connect/juno-qqbot](https://github.com/tencent-connect/juno-qqbot)

```bash
juno plugins install @tencent-connect/juno-qqbot
```

### wecom

WeCom channel plugin for Juno by the Tencent WeCom team. Powered by
WeCom Bot WebSocket persistent connections, it supports direct messages & group
chats, streaming replies, proactive messaging, image/file processing, Markdown
formatting, built-in access control, and document/meeting/messaging skills.

- **npm:** `@wecom/wecom-juno-plugin`
- **repo:** [github.com/WecomTeam/wecom-juno-plugin](https://github.com/WecomTeam/wecom-juno-plugin)

```bash
juno plugins install @wecom/wecom-juno-plugin
```

## Submit your plugin

We welcome community plugins that are useful, documented, and safe to operate.

<Steps>
  <Step title="Publish to JunoHub or npm">
    Your plugin must be installable via `juno plugins install \<package-name\>`.
    Publish to [JunoHub](/tools/junohub) (preferred) or npm.
    See [Building Plugins](/plugins/building-plugins) for the full guide.

  </Step>

  <Step title="Host on GitHub">
    Source code must be in a public repository with setup docs and an issue
    tracker.

  </Step>

  <Step title="Use docs PRs only for source-doc changes">
    You do not need a docs PR just to make your plugin discoverable. Publish it
    on JunoHub instead.

    Open a docs PR only when Juno's source docs need an actual content
    change, such as correcting install guidance or adding cross-repo
    documentation that belongs in the main docs set.

  </Step>
</Steps>

## Quality bar

| Requirement                 | Why                                           |
| --------------------------- | --------------------------------------------- |
| Published on JunoHub or npm | Users need `juno plugins install` to work |
| Public GitHub repo          | Source review, issue tracking, transparency   |
| Setup and usage docs        | Users need to know how to configure it        |
| Active maintenance          | Recent updates or responsive issue handling   |

Low-effort wrappers, unclear ownership, or unmaintained packages may be declined.

## Related

- [Install and Configure Plugins](/tools/plugin) — how to install any plugin
- [Building Plugins](/plugins/building-plugins) — create your own
- [Plugin Manifest](/plugins/manifest) — manifest schema
