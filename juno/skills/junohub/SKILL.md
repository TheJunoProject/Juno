---
name: junohub
description: Use the JunoHub CLI to search, install, update, and publish agent skills from junohub.com. Use when you need to fetch new skills on the fly, sync installed skills to latest or a specific version, or publish new/updated skill folders with the npm-installed junohub CLI.
metadata:
  {
    "juno":
      {
        "requires": { "bins": ["junohub"] },
        "install":
          [
            {
              "id": "node",
              "kind": "node",
              "package": "junohub",
              "bins": ["junohub"],
              "label": "Install JunoHub CLI (npm)",
            },
          ],
      },
  }
---

# JunoHub CLI

Install

```bash
npm i -g junohub
```

Auth (publish)

```bash
junohub login
junohub whoami
```

Search

```bash
junohub search "postgres backups"
```

Install

```bash
junohub install my-skill
junohub install my-skill --version 1.2.3
```

Update (hash-based match + upgrade)

```bash
junohub update my-skill
junohub update my-skill --version 1.2.3
junohub update --all
junohub update my-skill --force
junohub update --all --no-input --force
```

List

```bash
junohub list
```

Publish

```bash
junohub publish ./my-skill --slug my-skill --name "My Skill" --version 1.2.0 --changelog "Fixes + docs"
```

Notes

- Default registry: https://junohub.com (override with JUNOHUB_REGISTRY or --registry)
- Default workdir: cwd (falls back to Juno workspace); install dir: ./skills (override with --workdir / --dir / JUNOHUB_WORKDIR)
- Update command hashes local files, resolves matching version, and upgrades to latest unless --version is set
