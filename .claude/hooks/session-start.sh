#!/bin/bash
# SessionStart hook for Claude Code on the web.
# Prepares a fresh cloud VM the same way CI does (.github/workflows/test.yml)
# so `uv run pytest` works without manual setup.
set -euo pipefail

# Local sessions keep using the developer's own environment and .env.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# .env is git-ignored, so the cloud clone has no CONFIG_HOOK. Default it to
# repom's hook while keeping a value set in the cloud environment settings;
# the single-quoted line is expanded when Claude Code sources the file.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  # shellcheck disable=SC2016
  echo 'export CONFIG_HOOK="${CONFIG_HOOK:-repom.config_hook:hook_config}"' >> "$CLAUDE_ENV_FILE"
fi

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# --all-extras is required: tests import asyncpg, psycopg and redis.
# On failure, print a readable first line and exit 1 so Claude Code reports
# a non-blocking hook error; the session still starts.
if ! output="$(uv sync --all-extras --dev --locked 2>&1)"; then
  printf 'uv sync --all-extras --dev --locked failed:\n%s\n' "$output" >&2
  exit 1
fi
