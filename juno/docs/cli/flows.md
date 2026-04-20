---
summary: "Redirect: flow commands live under `juno tasks flow`"
read_when:
  - You encounter juno flows in older docs or release notes
title: "flows (redirect)"
---

# `juno tasks flow`

Flow commands are subcommands of `juno tasks`, not a standalone `flows` command.

```bash
juno tasks flow list [--json]
juno tasks flow show <lookup>
juno tasks flow cancel <lookup>
```

For full documentation see [Task Flow](/automation/taskflow) and the [tasks CLI reference](/cli/index#tasks).
