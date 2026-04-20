#!/usr/bin/env bash
# JunoDock - Docker helpers for Juno
# Inspired by Simon Willison's "Running Juno in Docker"
# https://til.simonwillison.net/llms/juno-docker
#
# Installation:
#   mkdir -p ~/.junodock && curl -sL https://raw.githubusercontent.com/juno/juno/main/scripts/junodock/junodock-helpers.sh -o ~/.junodock/junodock-helpers.sh
#   echo 'source ~/.junodock/junodock-helpers.sh' >> ~/.zshrc
#
# Usage:
#   junodock-help    # Show all available commands

# =============================================================================
# Colors
# =============================================================================
_CLR_RESET='\033[0m'
_CLR_BOLD='\033[1m'
_CLR_DIM='\033[2m'
_CLR_GREEN='\033[0;32m'
_CLR_YELLOW='\033[1;33m'
_CLR_BLUE='\033[0;34m'
_CLR_MAGENTA='\033[0;35m'
_CLR_CYAN='\033[0;36m'
_CLR_RED='\033[0;31m'

# Styled command output (green + bold)
_clr_cmd() {
  echo -e "${_CLR_GREEN}${_CLR_BOLD}$1${_CLR_RESET}"
}

# Inline command for use in sentences
_cmd() {
  echo "${_CLR_GREEN}${_CLR_BOLD}$1${_CLR_RESET}"
}

# =============================================================================
# Config
# =============================================================================
JUNODOCK_CONFIG="${HOME}/.junodock/config"

# Common paths to check for Juno
JUNODOCK_COMMON_PATHS=(
  "${HOME}/juno"
  "${HOME}/workspace/juno"
  "${HOME}/projects/juno"
  "${HOME}/dev/juno"
  "${HOME}/code/juno"
  "${HOME}/src/juno"
)

_junodock_filter_warnings() {
  grep -v "^WARN\|^time="
}

_junodock_trim_quotes() {
  local value="$1"
  value="${value#\"}"
  value="${value%\"}"
  printf "%s" "$value"
}

_junodock_mask_value() {
  local value="$1"
  local length=${#value}
  if (( length == 0 )); then
    printf "%s" "<empty>"
    return 0
  fi
  if (( length == 1 )); then
    printf "%s" "<redacted:1 char>"
    return 0
  fi
  printf "%s" "<redacted:${length} chars>"
}

_junodock_read_config_dir() {
  if [[ ! -f "$JUNODOCK_CONFIG" ]]; then
    return 1
  fi
  local raw
  raw=$(sed -n 's/^JUNODOCK_DIR=//p' "$JUNODOCK_CONFIG" | head -n 1)
  if [[ -z "$raw" ]]; then
    return 1
  fi
  _junodock_trim_quotes "$raw"
}

# Ensure JUNODOCK_DIR is set and valid
_junodock_ensure_dir() {
  # Already set and valid?
  if [[ -n "$JUNODOCK_DIR" && -f "${JUNODOCK_DIR}/docker-compose.yml" ]]; then
    return 0
  fi

  # Try loading from config
  local config_dir
  config_dir=$(_junodock_read_config_dir)
  if [[ -n "$config_dir" && -f "${config_dir}/docker-compose.yml" ]]; then
    JUNODOCK_DIR="$config_dir"
    return 0
  fi

  # Auto-detect from common paths
  local found_path=""
  for path in "${JUNODOCK_COMMON_PATHS[@]}"; do
    if [[ -f "${path}/docker-compose.yml" ]]; then
      found_path="$path"
      break
    fi
  done

  if [[ -n "$found_path" ]]; then
    echo ""
    echo "🦞 Found Juno at: $found_path"
    echo -n "   Use this location? [Y/n] "
    read -r response
    if [[ "$response" =~ ^[Nn] ]]; then
      echo ""
      echo "Set JUNODOCK_DIR manually:"
      echo "  export JUNODOCK_DIR=/path/to/juno"
      return 1
    fi
    JUNODOCK_DIR="$found_path"
  else
    echo ""
    echo "❌ Juno not found in common locations."
    echo ""
    echo "Clone it first:"
    echo ""
    echo "  git clone https://github.com/juno/juno.git ~/juno"
    echo "  cd ~/juno && ./scripts/docker/setup.sh"
    echo ""
    echo "Or set JUNODOCK_DIR if it's elsewhere:"
    echo ""
    echo "  export JUNODOCK_DIR=/path/to/juno"
    echo ""
    return 1
  fi

  # Save to config
  if [[ ! -d "${HOME}/.junodock" ]]; then
    /bin/mkdir -p "${HOME}/.junodock"
  fi
  echo "JUNODOCK_DIR=\"$JUNODOCK_DIR\"" > "$JUNODOCK_CONFIG"
  echo "✅ Saved to $JUNODOCK_CONFIG"
  echo ""
  return 0
}

# Wrapper to run docker compose commands
_junodock_compose() {
  _junodock_ensure_dir || return 1
  local compose_args=(-f "${JUNODOCK_DIR}/docker-compose.yml")
  if [[ -f "${JUNODOCK_DIR}/docker-compose.extra.yml" ]]; then
    compose_args+=(-f "${JUNODOCK_DIR}/docker-compose.extra.yml")
  fi
  command docker compose "${compose_args[@]}" "$@"
}

_junodock_read_env_token() {
  _junodock_ensure_dir || return 1
  if [[ ! -f "${JUNODOCK_DIR}/.env" ]]; then
    return 1
  fi
  local raw
  raw=$(sed -n 's/^JUNO_GATEWAY_TOKEN=//p' "${JUNODOCK_DIR}/.env" | head -n 1)
  if [[ -z "$raw" ]]; then
    return 1
  fi
  _junodock_trim_quotes "$raw"
}

# Basic Operations
junodock-start() {
  _junodock_compose up -d juno-gateway
}

junodock-stop() {
  _junodock_compose down
}

junodock-restart() {
  _junodock_compose restart juno-gateway
}

junodock-logs() {
  _junodock_compose logs -f juno-gateway
}

junodock-status() {
  _junodock_compose ps
}

# Navigation
junodock-cd() {
  _junodock_ensure_dir || return 1
  cd "${JUNODOCK_DIR}"
}

junodock-config() {
  cd ~/.juno
}

junodock-show-config() {
  _junodock_ensure_dir >/dev/null 2>&1 || true
  local config_dir="${HOME}/.juno"
  echo -e "${_CLR_BOLD}Config directory:${_CLR_RESET} ${_CLR_CYAN}${config_dir}${_CLR_RESET}"
  echo ""

  # Show juno.json
  if [[ -f "${config_dir}/juno.json" ]]; then
    echo -e "${_CLR_BOLD}${config_dir}/juno.json${_CLR_RESET}"
    echo -e "${_CLR_DIM}$(cat "${config_dir}/juno.json")${_CLR_RESET}"
  else
    echo -e "${_CLR_YELLOW}No juno.json found${_CLR_RESET}"
  fi
  echo ""

  # Show .env (mask secret values)
  if [[ -f "${config_dir}/.env" ]]; then
    echo -e "${_CLR_BOLD}${config_dir}/.env${_CLR_RESET}"
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
        echo -e "${_CLR_DIM}${line}${_CLR_RESET}"
      elif [[ "$line" == *=* ]]; then
        local key="${line%%=*}"
        local val="${line#*=}"
        echo -e "${_CLR_CYAN}${key}${_CLR_RESET}=${_CLR_DIM}$(_junodock_mask_value "$val")${_CLR_RESET}"
      else
        echo -e "${_CLR_DIM}${line}${_CLR_RESET}"
      fi
    done < "${config_dir}/.env"
  else
    echo -e "${_CLR_YELLOW}No .env found${_CLR_RESET}"
  fi
  echo ""

  # Show project .env if available
  if [[ -n "$JUNODOCK_DIR" && -f "${JUNODOCK_DIR}/.env" ]]; then
    echo -e "${_CLR_BOLD}${JUNODOCK_DIR}/.env${_CLR_RESET}"
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
        echo -e "${_CLR_DIM}${line}${_CLR_RESET}"
      elif [[ "$line" == *=* ]]; then
        local key="${line%%=*}"
        local val="${line#*=}"
        echo -e "${_CLR_CYAN}${key}${_CLR_RESET}=${_CLR_DIM}$(_junodock_mask_value "$val")${_CLR_RESET}"
      else
        echo -e "${_CLR_DIM}${line}${_CLR_RESET}"
      fi
    done < "${JUNODOCK_DIR}/.env"
  fi
  echo ""
}

junodock-workspace() {
  cd ~/.juno/workspace
}

# Container Access
junodock-shell() {
  _junodock_compose exec juno-gateway \
    bash -c 'echo "alias juno=\"./juno.mjs\"" > /tmp/.bashrc_juno && bash --rcfile /tmp/.bashrc_juno'
}

junodock-exec() {
  _junodock_compose exec juno-gateway "$@"
}

junodock-cli() {
  _junodock_compose run --rm juno-cli "$@"
}

# Maintenance
junodock-update() {
  _junodock_ensure_dir || return 1

  echo "🔄 Updating Juno..."

  echo ""
  echo "📥 Pulling latest source..."
  git -C "${JUNODOCK_DIR}" pull || { echo "❌ git pull failed"; return 1; }

  echo ""
  echo "🔨 Rebuilding Docker image (this may take a few minutes)..."
  _junodock_compose build juno-gateway || { echo "❌ Build failed"; return 1; }

  echo ""
  echo "♻️  Recreating container with new image..."
  _junodock_compose down 2>&1 | _junodock_filter_warnings
  _junodock_compose up -d juno-gateway 2>&1 | _junodock_filter_warnings

  echo ""
  echo "⏳ Waiting for gateway to start..."
  sleep 5

  echo "✅ Update complete!"
  echo -e "   Verify: $(_cmd junodock-cli status)"
}

junodock-rebuild() {
  _junodock_compose build juno-gateway
}

junodock-clean() {
  _junodock_compose down -v --remove-orphans
}

# Health check
junodock-health() {
  _junodock_ensure_dir || return 1
  local token
  token=$(_junodock_read_env_token)
  if [[ -z "$token" ]]; then
    echo "❌ Error: Could not find gateway token"
    echo "   Check: ${JUNODOCK_DIR}/.env"
    return 1
  fi
  _junodock_compose exec -e "JUNO_GATEWAY_TOKEN=$token" juno-gateway \
    node dist/index.js health
}

# Show gateway token
junodock-token() {
  _junodock_read_env_token
}

# Fix token configuration (run this once after setup)
junodock-fix-token() {
  _junodock_ensure_dir || return 1

  echo "🔧 Configuring gateway token..."
  local token
  token=$(junodock-token)
  if [[ -z "$token" ]]; then
    echo "❌ Error: Could not find gateway token"
    echo "   Check: ${JUNODOCK_DIR}/.env"
    return 1
  fi

  echo "📝 Setting token: ${token:0:20}..."

  _junodock_compose exec -e "TOKEN=$token" juno-gateway \
    bash -c './juno.mjs config set gateway.remote.token "$TOKEN" && ./juno.mjs config set gateway.auth.token "$TOKEN"' 2>&1 | _junodock_filter_warnings

  echo "🔍 Verifying token was saved..."
  local saved_token
  saved_token=$(_junodock_compose exec juno-gateway \
    bash -c "./juno.mjs config get gateway.remote.token 2>/dev/null" 2>&1 | _junodock_filter_warnings | tr -d '\r\n' | head -c 64)

  if [[ "$saved_token" == "$token" ]]; then
    echo "✅ Token saved correctly!"
  else
    echo "⚠️  Token mismatch detected"
    echo "   Expected: ${token:0:20}..."
    echo "   Got: ${saved_token:0:20}..."
  fi

  echo "🔄 Restarting gateway..."
  _junodock_compose restart juno-gateway 2>&1 | _junodock_filter_warnings

  echo "⏳ Waiting for gateway to start..."
  sleep 5

  echo "✅ Configuration complete!"
  echo -e "   Try: $(_cmd junodock-devices)"
}

# Open dashboard in browser
junodock-dashboard() {
  _junodock_ensure_dir || return 1

  echo "🦞 Getting dashboard URL..."
  local output exit_status url
  output=$(_junodock_compose run --rm juno-cli dashboard --no-open 2>&1)
  exit_status=$?
  url=$(printf "%s\n" "$output" | _junodock_filter_warnings | grep -o 'http[s]\?://[^[:space:]]*' | head -n 1)
  if [[ $exit_status -ne 0 ]]; then
    echo "❌ Failed to get dashboard URL"
    echo -e "   Try restarting: $(_cmd junodock-restart)"
    return 1
  fi

  if [[ -n "$url" ]]; then
    echo -e "✅ Opening: ${_CLR_CYAN}${url}${_CLR_RESET}"
    open "$url" 2>/dev/null || xdg-open "$url" 2>/dev/null || echo -e "   Please open manually: ${_CLR_CYAN}${url}${_CLR_RESET}"
    echo ""
    echo -e "${_CLR_CYAN}💡 If you see ${_CLR_RED}'pairing required'${_CLR_CYAN} error:${_CLR_RESET}"
    echo -e "   1. Run: $(_cmd junodock-devices)"
    echo "   2. Copy the Request ID from the Pending table"
    echo -e "   3. Run: $(_cmd 'junodock-approve <request-id>')"
  else
    echo "❌ Failed to get dashboard URL"
    echo -e "   Try restarting: $(_cmd junodock-restart)"
  fi
}

# List device pairings
junodock-devices() {
  _junodock_ensure_dir || return 1

  echo "🔍 Checking device pairings..."
  local output exit_status
  output=$(_junodock_compose exec juno-gateway node dist/index.js devices list 2>&1)
  exit_status=$?
  printf "%s\n" "$output" | _junodock_filter_warnings
  if [ $exit_status -ne 0 ]; then
    echo ""
    echo -e "${_CLR_CYAN}💡 If you see token errors above:${_CLR_RESET}"
    echo -e "   1. Verify token is set: $(_cmd junodock-token)"
    echo -e "   2. Try fixing the token automatically: $(_cmd junodock-fix-token)"
    echo "   3. If you still see errors, try manual config inside container:"
    echo -e "      $(_cmd junodock-shell)"
    echo -e "      $(_cmd 'juno config get gateway.remote.token')"
    return 1
  fi

  echo ""
  echo -e "${_CLR_CYAN}💡 To approve a pairing request:${_CLR_RESET}"
  echo -e "   $(_cmd 'junodock-approve <request-id>')"
}

# Approve device pairing request
junodock-approve() {
  _junodock_ensure_dir || return 1

  if [[ -z "$1" ]]; then
    echo -e "❌ Usage: $(_cmd 'junodock-approve <request-id>')"
    echo ""
    echo -e "${_CLR_CYAN}💡 How to approve a device:${_CLR_RESET}"
    echo -e "   1. Run: $(_cmd junodock-devices)"
    echo "   2. Find the Request ID in the Pending table (long UUID)"
    echo -e "   3. Run: $(_cmd 'junodock-approve <that-request-id>')"
    echo ""
    echo "Example:"
    echo -e "   $(_cmd 'junodock-approve 6f9db1bd-a1cc-4d3f-b643-2c195262464e')"
    return 1
  fi

  echo "✅ Approving device: $1"
  _junodock_compose exec juno-gateway \
    node dist/index.js devices approve "$1" 2>&1 | _junodock_filter_warnings

  echo ""
  echo "✅ Device approved! Refresh your browser."
}

# Show all available junodock helper commands
junodock-help() {
  echo -e "\n${_CLR_BOLD}${_CLR_CYAN}🦞 JunoDock - Docker Helpers for Juno${_CLR_RESET}\n"

  echo -e "${_CLR_BOLD}${_CLR_MAGENTA}⚡ Basic Operations${_CLR_RESET}"
  echo -e "  $(_cmd junodock-start)       ${_CLR_DIM}Start the gateway${_CLR_RESET}"
  echo -e "  $(_cmd junodock-stop)        ${_CLR_DIM}Stop the gateway${_CLR_RESET}"
  echo -e "  $(_cmd junodock-restart)     ${_CLR_DIM}Restart the gateway${_CLR_RESET}"
  echo -e "  $(_cmd junodock-status)      ${_CLR_DIM}Check container status${_CLR_RESET}"
  echo -e "  $(_cmd junodock-logs)        ${_CLR_DIM}View live logs (follows)${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_MAGENTA}🐚 Container Access${_CLR_RESET}"
  echo -e "  $(_cmd junodock-shell)       ${_CLR_DIM}Shell into container (juno alias ready)${_CLR_RESET}"
  echo -e "  $(_cmd junodock-cli)         ${_CLR_DIM}Run CLI commands (e.g., junodock-cli status)${_CLR_RESET}"
  echo -e "  $(_cmd junodock-exec) ${_CLR_CYAN}<cmd>${_CLR_RESET}  ${_CLR_DIM}Execute command in gateway container${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_MAGENTA}🌐 Web UI & Devices${_CLR_RESET}"
  echo -e "  $(_cmd junodock-dashboard)   ${_CLR_DIM}Open web UI in browser ${_CLR_CYAN}(auto-guides you)${_CLR_RESET}"
  echo -e "  $(_cmd junodock-devices)     ${_CLR_DIM}List device pairings ${_CLR_CYAN}(auto-guides you)${_CLR_RESET}"
  echo -e "  $(_cmd junodock-approve) ${_CLR_CYAN}<id>${_CLR_RESET} ${_CLR_DIM}Approve device pairing ${_CLR_CYAN}(with examples)${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_MAGENTA}⚙️  Setup & Configuration${_CLR_RESET}"
  echo -e "  $(_cmd junodock-fix-token)   ${_CLR_DIM}Configure gateway token ${_CLR_CYAN}(run once)${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_MAGENTA}🔧 Maintenance${_CLR_RESET}"
  echo -e "  $(_cmd junodock-update)      ${_CLR_DIM}Pull, rebuild, and restart ${_CLR_CYAN}(one-command update)${_CLR_RESET}"
  echo -e "  $(_cmd junodock-rebuild)     ${_CLR_DIM}Rebuild Docker image only${_CLR_RESET}"
  echo -e "  $(_cmd junodock-clean)       ${_CLR_RED}⚠️  Remove containers & volumes (nuclear)${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_MAGENTA}🛠️  Utilities${_CLR_RESET}"
  echo -e "  $(_cmd junodock-health)      ${_CLR_DIM}Run health check${_CLR_RESET}"
  echo -e "  $(_cmd junodock-token)       ${_CLR_DIM}Show gateway auth token${_CLR_RESET}"
  echo -e "  $(_cmd junodock-cd)          ${_CLR_DIM}Jump to juno project directory${_CLR_RESET}"
  echo -e "  $(_cmd junodock-config)      ${_CLR_DIM}Open config directory (~/.juno)${_CLR_RESET}"
  echo -e "  $(_cmd junodock-show-config) ${_CLR_DIM}Print config files with redacted values${_CLR_RESET}"
  echo -e "  $(_cmd junodock-workspace)   ${_CLR_DIM}Open workspace directory${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${_CLR_RESET}"
  echo -e "${_CLR_BOLD}${_CLR_GREEN}🚀 First Time Setup${_CLR_RESET}"
  echo -e "${_CLR_CYAN}  1.${_CLR_RESET} $(_cmd junodock-start)          ${_CLR_DIM}# Start the gateway${_CLR_RESET}"
  echo -e "${_CLR_CYAN}  2.${_CLR_RESET} $(_cmd junodock-fix-token)      ${_CLR_DIM}# Configure token${_CLR_RESET}"
  echo -e "${_CLR_CYAN}  3.${_CLR_RESET} $(_cmd junodock-dashboard)      ${_CLR_DIM}# Open web UI${_CLR_RESET}"
  echo -e "${_CLR_CYAN}  4.${_CLR_RESET} $(_cmd junodock-devices)        ${_CLR_DIM}# If pairing needed${_CLR_RESET}"
  echo -e "${_CLR_CYAN}  5.${_CLR_RESET} $(_cmd junodock-approve) ${_CLR_CYAN}<id>${_CLR_RESET}   ${_CLR_DIM}# Approve pairing${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_GREEN}💬 WhatsApp Setup${_CLR_RESET}"
  echo -e "  $(_cmd junodock-shell)"
  echo -e "    ${_CLR_BLUE}>${_CLR_RESET} $(_cmd 'juno channels login --channel whatsapp')"
  echo -e "    ${_CLR_BLUE}>${_CLR_RESET} $(_cmd 'juno status')"
  echo ""

  echo -e "${_CLR_BOLD}${_CLR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${_CLR_RESET}"
  echo ""

  echo -e "${_CLR_CYAN}💡 All commands guide you through next steps!${_CLR_RESET}"
  echo -e "${_CLR_BLUE}📚 Docs: ${_CLR_RESET}${_CLR_CYAN}https://docs.juno.ai${_CLR_RESET}"
  echo ""
}
