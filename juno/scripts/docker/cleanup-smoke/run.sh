#!/usr/bin/env bash
set -euo pipefail

cd /repo

export JUNO_STATE_DIR="/tmp/juno-test"
export JUNO_CONFIG_PATH="${JUNO_STATE_DIR}/juno.json"

echo "==> Build"
if ! pnpm build >/tmp/juno-cleanup-build.log 2>&1; then
  cat /tmp/juno-cleanup-build.log
  exit 1
fi

echo "==> Seed state"
mkdir -p "${JUNO_STATE_DIR}/credentials"
mkdir -p "${JUNO_STATE_DIR}/agents/main/sessions"
echo '{}' >"${JUNO_CONFIG_PATH}"
echo 'creds' >"${JUNO_STATE_DIR}/credentials/marker.txt"
echo 'session' >"${JUNO_STATE_DIR}/agents/main/sessions/sessions.json"

echo "==> Reset (config+creds+sessions)"
if ! pnpm juno reset --scope config+creds+sessions --yes --non-interactive >/tmp/juno-cleanup-reset.log 2>&1; then
  cat /tmp/juno-cleanup-reset.log
  exit 1
fi

test ! -f "${JUNO_CONFIG_PATH}"
test ! -d "${JUNO_STATE_DIR}/credentials"
test ! -d "${JUNO_STATE_DIR}/agents/main/sessions"

echo "==> Recreate minimal config"
mkdir -p "${JUNO_STATE_DIR}/credentials"
echo '{}' >"${JUNO_CONFIG_PATH}"

echo "==> Uninstall (state only)"
if ! pnpm juno uninstall --state --yes --non-interactive >/tmp/juno-cleanup-uninstall.log 2>&1; then
  cat /tmp/juno-cleanup-uninstall.log
  exit 1
fi

test ! -d "${JUNO_STATE_DIR}"

echo "OK"
