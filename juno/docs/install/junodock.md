---
summary: "JunoDock shell helpers for Docker-based Juno installs"
read_when:
  - You run Juno with Docker often and want shorter day-to-day commands
  - You want a helper layer for dashboard, logs, token setup, and pairing flows
title: "JunoDock"
---

# JunoDock

JunoDock is a small shell-helper layer for Docker-based Juno installs.

It gives you short commands like `junodock-start`, `junodock-dashboard`, and `junodock-fix-token` instead of longer `docker compose ...` invocations.

If you have not set up Docker yet, start with [Docker](/install/docker).

## Install

Use the canonical helper path:

```bash
mkdir -p ~/.junodock && curl -sL https://raw.githubusercontent.com/juno/juno/main/scripts/junodock/junodock-helpers.sh -o ~/.junodock/junodock-helpers.sh
echo 'source ~/.junodock/junodock-helpers.sh' >> ~/.zshrc && source ~/.zshrc
```

If you previously installed JunoDock from `scripts/shell-helpers/junodock-helpers.sh`, reinstall from the new `scripts/junodock/junodock-helpers.sh` path. The old raw GitHub path was removed.

## What you get

### Basic operations

| Command            | Description            |
| ------------------ | ---------------------- |
| `junodock-start`   | Start the gateway      |
| `junodock-stop`    | Stop the gateway       |
| `junodock-restart` | Restart the gateway    |
| `junodock-status`  | Check container status |
| `junodock-logs`    | Follow gateway logs    |

### Container access

| Command                   | Description                                   |
| ------------------------- | --------------------------------------------- |
| `junodock-shell`          | Open a shell inside the gateway container     |
| `junodock-cli <command>`  | Run Juno CLI commands in Docker           |
| `junodock-exec <command>` | Execute an arbitrary command in the container |

### Web UI and pairing

| Command                 | Description                  |
| ----------------------- | ---------------------------- |
| `junodock-dashboard`    | Open the Control UI URL      |
| `junodock-devices`      | List pending device pairings |
| `junodock-approve <id>` | Approve a pairing request    |

### Setup and maintenance

| Command              | Description                                      |
| -------------------- | ------------------------------------------------ |
| `junodock-fix-token` | Configure the gateway token inside the container |
| `junodock-update`    | Pull, rebuild, and restart                       |
| `junodock-rebuild`   | Rebuild the Docker image only                    |
| `junodock-clean`     | Remove containers and volumes                    |

### Utilities

| Command                | Description                             |
| ---------------------- | --------------------------------------- |
| `junodock-health`      | Run a gateway health check              |
| `junodock-token`       | Print the gateway token                 |
| `junodock-cd`          | Jump to the Juno project directory  |
| `junodock-config`      | Open `~/.juno`                      |
| `junodock-show-config` | Print config files with redacted values |
| `junodock-workspace`   | Open the workspace directory            |

## First-time flow

```bash
junodock-start
junodock-fix-token
junodock-dashboard
```

If the browser says pairing is required:

```bash
junodock-devices
junodock-approve <request-id>
```

## Config and secrets

JunoDock works with the same Docker config split described in [Docker](/install/docker):

- `<project>/.env` for Docker-specific values like image name, ports, and the gateway token
- `~/.juno/.env` for env-backed provider keys and bot tokens
- `~/.juno/agents/<agentId>/agent/auth-profiles.json` for stored provider OAuth/API-key auth
- `~/.juno/juno.json` for behavior config

Use `junodock-show-config` when you want to inspect the `.env` files and `juno.json` quickly. It redacts `.env` values in its printed output.

## Related pages

- [Docker](/install/docker)
- [Docker VM Runtime](/install/docker-vm-runtime)
- [Updating](/install/updating)
