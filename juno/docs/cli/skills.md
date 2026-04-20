---
summary: "CLI reference for `juno skills` (search/install/update/list/info/check)"
read_when:
  - You want to see which skills are available and ready to run
  - You want to search, install, or update skills from JunoHub
  - You want to debug missing binaries/env/config for skills
title: "skills"
---

# `juno skills`

Inspect local skills and install/update skills from JunoHub.

Related:

- Skills system: [Skills](/tools/skills)
- Skills config: [Skills config](/tools/skills-config)
- JunoHub installs: [JunoHub](/tools/junohub)

## Commands

```bash
juno skills search "calendar"
juno skills search --limit 20 --json
juno skills install <slug>
juno skills install <slug> --version <version>
juno skills install <slug> --force
juno skills update <slug>
juno skills update --all
juno skills list
juno skills list --eligible
juno skills list --json
juno skills list --verbose
juno skills info <name>
juno skills info <name> --json
juno skills check
juno skills check --json
```

`search`/`install`/`update` use JunoHub directly and install into the active
workspace `skills/` directory. `list`/`info`/`check` still inspect the local
skills visible to the current workspace and config.

This CLI `install` command downloads skill folders from JunoHub. Gateway-backed
skill dependency installs triggered from onboarding or Skills settings use the
separate `skills.install` request path instead.

Notes:

- `search [query...]` accepts an optional query; omit it to browse the default
  JunoHub search feed.
- `search --limit <n>` caps returned results.
- `install --force` overwrites an existing workspace skill folder for the same
  slug.
- `update --all` only updates tracked JunoHub installs in the active workspace.
- `list` is the default action when no subcommand is provided.
- `list`, `info`, and `check` write their rendered output to stdout. With
  `--json`, that means the machine-readable payload stays on stdout for pipes
  and scripts.
