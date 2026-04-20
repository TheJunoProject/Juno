#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${JUNO_INSTALL_E2E_IMAGE:-juno-install-e2e:local}"
INSTALL_URL="${JUNO_INSTALL_URL:-https://juno.bot/install.sh}"

OPENAI_API_KEY="${OPENAI_API_KEY:-}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
ANTHROPIC_API_TOKEN="${ANTHROPIC_API_TOKEN:-}"
JUNO_E2E_MODELS="${JUNO_E2E_MODELS:-}"

echo "==> Build image: $IMAGE_NAME"
docker build \
  -t "$IMAGE_NAME" \
  -f "$ROOT_DIR/scripts/docker/install-sh-e2e/Dockerfile" \
  "$ROOT_DIR/scripts/docker"

echo "==> Run E2E installer test"
docker run --rm \
  -e JUNO_INSTALL_URL="$INSTALL_URL" \
  -e JUNO_INSTALL_TAG="${JUNO_INSTALL_TAG:-latest}" \
  -e JUNO_E2E_MODELS="$JUNO_E2E_MODELS" \
  -e JUNO_INSTALL_E2E_PREVIOUS="${JUNO_INSTALL_E2E_PREVIOUS:-}" \
  -e JUNO_INSTALL_E2E_SKIP_PREVIOUS="${JUNO_INSTALL_E2E_SKIP_PREVIOUS:-0}" \
  -e JUNO_NO_ONBOARD=1 \
  -e OPENAI_API_KEY \
  -e ANTHROPIC_API_KEY \
  -e ANTHROPIC_API_TOKEN \
  "$IMAGE_NAME"
