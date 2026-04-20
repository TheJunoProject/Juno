---
summary: "CLI reference for `juno voicecall` (voice-call plugin command surface)"
read_when:
  - You use the voice-call plugin and want the CLI entry points
  - You want quick examples for `voicecall call|continue|status|tail|expose`
title: "voicecall"
---

# `juno voicecall`

`voicecall` is a plugin-provided command. It only appears if the voice-call plugin is installed and enabled.

Primary doc:

- Voice-call plugin: [Voice Call](/plugins/voice-call)

## Common commands

```bash
juno voicecall status --call-id <id>
juno voicecall call --to "+15555550123" --message "Hello" --mode notify
juno voicecall continue --call-id <id> --message "Any questions?"
juno voicecall end --call-id <id>
```

## Exposing webhooks (Tailscale)

```bash
juno voicecall expose --mode serve
juno voicecall expose --mode funnel
juno voicecall expose --mode off
```

Security note: only expose the webhook endpoint to networks you trust. Prefer Tailscale Serve over Funnel when possible.
