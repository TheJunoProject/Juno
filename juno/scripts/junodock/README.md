# JunoDock <!-- omit in toc -->

Stop typing `docker-compose` commands. Just type `junodock-start`.

Inspired by Simon Willison's [Running Juno in Docker](https://til.simonwillison.net/llms/juno-docker).

- [Quickstart](#quickstart)
- [Available Commands](#available-commands)
  - [Basic Operations](#basic-operations)
  - [Container Access](#container-access)
  - [Web UI \& Devices](#web-ui--devices)
  - [Setup \& Configuration](#setup--configuration)
  - [Maintenance](#maintenance)
  - [Utilities](#utilities)
- [Configuration \& Secrets](#configuration--secrets)
  - [Docker Files](#docker-files)
  - [Config Files](#config-files)
  - [Initial Setup](#initial-setup)
  - [How It Works in Docker](#how-it-works-in-docker)
  - [Env Precedence](#env-precedence)
- [Common Workflows](#common-workflows)
  - [Check Status and Logs](#check-status-and-logs)
  - [Set Up WhatsApp Bot](#set-up-whatsapp-bot)
  - [Troubleshooting Device Pairing](#troubleshooting-device-pairing)
  - [Fix Token Mismatch Issues](#fix-token-mismatch-issues)
  - [Permission Denied](#permission-denied)
- [Requirements](#requirements)
- [Development](#development)

## Quickstart

**Install:**

```bash
mkdir -p ~/.junodock && curl -sL https://raw.githubusercontent.com/juno/juno/main/scripts/junodock/junodock-helpers.sh -o ~/.junodock/junodock-helpers.sh
```

```bash
echo 'source ~/.junodock/junodock-helpers.sh' >> ~/.zshrc && source ~/.zshrc
```

Canonical docs page: https://docs.juno.ai/install/junodock

If you previously installed JunoDock from `scripts/shell-helpers/junodock-helpers.sh`, rerun the install command above. The old raw GitHub path has been removed.

**See what you get:**

```bash
junodock-help
```

On first command, JunoDock auto-detects your Juno directory:

- Checks common paths (`~/juno`, `~/workspace/juno`, etc.)
- If found, asks you to confirm
- Saves to `~/.junodock/config`

**First time setup:**

```bash
junodock-start
```

```bash
junodock-fix-token
```

```bash
junodock-dashboard
```

If you see "pairing required":

```bash
junodock-devices
```

And approve the request for the specific device:

```bash
junodock-approve <request-id>
```

## Available Commands

### Basic Operations

| Command            | Description                     |
| ------------------ | ------------------------------- |
| `junodock-start`   | Start the gateway               |
| `junodock-stop`    | Stop the gateway                |
| `junodock-restart` | Restart the gateway             |
| `junodock-status`  | Check container status          |
| `junodock-logs`    | View live logs (follows output) |

### Container Access

| Command                   | Description                                    |
| ------------------------- | ---------------------------------------------- |
| `junodock-shell`          | Interactive shell inside the gateway container |
| `junodock-cli <command>`  | Run Juno CLI commands                      |
| `junodock-exec <command>` | Execute arbitrary commands in the container    |

### Web UI & Devices

| Command                 | Description                                |
| ----------------------- | ------------------------------------------ |
| `junodock-dashboard`    | Open web UI in browser with authentication |
| `junodock-devices`      | List device pairing requests               |
| `junodock-approve <id>` | Approve a device pairing request           |

### Setup & Configuration

| Command              | Description                                       |
| -------------------- | ------------------------------------------------- |
| `junodock-fix-token` | Configure gateway authentication token (run once) |

### Maintenance

| Command            | Description                                           |
| ------------------ | ----------------------------------------------------- |
| `junodock-update`  | Pull latest, rebuild image, and restart (one command) |
| `junodock-rebuild` | Rebuild the Docker image only                         |
| `junodock-clean`   | Remove all containers and volumes (destructive!)      |

### Utilities

| Command                | Description                               |
| ---------------------- | ----------------------------------------- |
| `junodock-health`      | Run gateway health check                  |
| `junodock-token`       | Display the gateway authentication token  |
| `junodock-cd`          | Jump to the Juno project directory    |
| `junodock-config`      | Open the Juno config directory        |
| `junodock-show-config` | Print config files with redacted values   |
| `junodock-workspace`   | Open the workspace directory              |
| `junodock-help`        | Show all available commands with examples |

## Configuration & Secrets

The Docker setup uses three config files on the host. The container never stores secrets — everything is bind-mounted from local files.

### Docker Files

| File                       | Purpose                                                                    |
| -------------------------- | -------------------------------------------------------------------------- |
| `Dockerfile`               | Builds the `juno:local` image (Node 22, pnpm, non-root `node` user)    |
| `docker-compose.yml`       | Defines `juno-gateway` and `juno-cli` services, bind-mounts, ports |
| `docker-setup.sh`          | First-time setup — builds image, creates `.env` from `.env.example`        |
| `.env.example`             | Template for `<project>/.env` with all supported vars and docs             |
| `docker-compose.extra.yml` | Optional overrides — auto-loaded by JunoDock helpers if present            |

### Config Files

| File                        | Purpose                                          | Examples                                                            |
| --------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| `<project>/.env`            | **Docker infra** — image, ports, gateway token   | `JUNO_GATEWAY_TOKEN`, `JUNO_IMAGE`, `JUNO_GATEWAY_PORT` |
| `~/.juno/.env`          | **Secrets** — API keys and bot tokens            | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`         |
| `~/.juno/juno.json` | **Behavior config** — models, channels, policies | Model selection, WhatsApp allowlists, agent settings                |

**Do NOT** put API keys or bot tokens in `juno.json`. Use `~/.juno/.env` for all secrets.

### Initial Setup

`./docker-setup.sh` (in the project root) handles first-time Docker configuration:

- Builds the `juno:local` image from `Dockerfile`
- Creates `<project>/.env` from `.env.example` with a generated gateway token
- Sets up `~/.juno` directories if they don't exist

```bash
./docker-setup.sh
```

After setup, add your API keys:

```bash
vim ~/.juno/.env
```

See `.env.example` for all supported keys.

The `Dockerfile` supports two optional build args:

- `JUNO_DOCKER_APT_PACKAGES` — extra apt packages to install (e.g. `ffmpeg`)
- `JUNO_INSTALL_BROWSER=1` — pre-install Chromium for browser automation (adds ~300MB, but skips the 60-90s Playwright install on each container start)

### How It Works in Docker

`docker-compose.yml` bind-mounts both config and workspace from the host:

```yaml
volumes:
  - ${JUNO_CONFIG_DIR}:/home/node/.juno
  - ${JUNO_WORKSPACE_DIR}:/home/node/.juno/workspace
```

This means:

- `~/.juno/.env` is available inside the container at `/home/node/.juno/.env` — Juno loads it automatically as the global env fallback
- `~/.juno/juno.json` is available at `/home/node/.juno/juno.json` — the gateway watches it and hot-reloads most changes
- No need to add API keys to `docker-compose.yml` or configure anything inside the container
- Keys survive `junodock-update`, `junodock-rebuild`, and `junodock-clean` because they live on the host

The project `.env` feeds Docker Compose directly (gateway token, image name, ports). The `~/.juno/.env` feeds the Juno process inside the container.

### Example `~/.juno/.env`

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
```

### Example `<project>/.env`

```bash
JUNO_CONFIG_DIR=/Users/you/.juno
JUNO_WORKSPACE_DIR=/Users/you/.juno/workspace
JUNO_GATEWAY_PORT=18789
JUNO_BRIDGE_PORT=18790
JUNO_GATEWAY_BIND=lan
JUNO_GATEWAY_TOKEN=<generated-by-docker-setup>
JUNO_IMAGE=juno:local
```

### Env Precedence

Juno loads env vars in this order (highest wins, never overrides existing):

1. **Process environment** — `docker-compose.yml` `environment:` block (gateway token, session keys)
2. **`.env` in CWD** — project root `.env` (Docker infra vars)
3. **`~/.juno/.env`** — global secrets (API keys, bot tokens)
4. **`juno.json` `env` block** — inline vars, applied only if still missing
5. **Shell env import** — optional login-shell scrape (`JUNO_LOAD_SHELL_ENV=1`)

## Common Workflows

### Update Juno

> **Important:** `juno update` does not work inside Docker.
> The container runs as a non-root user with a source-built image, so `npm i -g` fails with EACCES.
> Use `junodock-update` instead — it pulls, rebuilds, and restarts from the host.

```bash
junodock-update
```

This runs `git pull` → `docker compose build` → `docker compose down/up` in one step.

If you only want to rebuild without pulling:

```bash
junodock-rebuild && junodock-stop && junodock-start
```

### Check Status and Logs

**Restart the gateway:**

```bash
junodock-restart
```

**Check container status:**

```bash
junodock-status
```

**View live logs:**

```bash
junodock-logs
```

### Set Up WhatsApp Bot

**Shell into the container:**

```bash
junodock-shell
```

**Inside the container, login to WhatsApp:**

```bash
juno channels login --channel whatsapp --verbose
```

Scan the QR code with WhatsApp on your phone.

**Verify connection:**

```bash
juno status
```

### Troubleshooting Device Pairing

**Check for pending pairing requests:**

```bash
junodock-devices
```

**Copy the Request ID from the "Pending" table, then approve:**

```bash
junodock-approve <request-id>
```

Then refresh your browser.

### Fix Token Mismatch Issues

If you see "gateway token mismatch" errors:

```bash
junodock-fix-token
```

This will:

1. Read the token from your `.env` file
2. Configure it in the Juno config
3. Restart the gateway
4. Verify the configuration

### Permission Denied

**Ensure Docker is running and you have permission:**

```bash
docker ps
```

## Requirements

- Docker and Docker Compose installed
- Bash or Zsh shell
- Juno project (run `scripts/docker/setup.sh`)

## Development

**Test with fresh config (mimics first-time install):**

```bash
unset JUNODOCK_DIR && rm -f ~/.junodock/config && source scripts/junodock/junodock-helpers.sh
```

Then run any command to trigger auto-detect:

```bash
junodock-start
```
