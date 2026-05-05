#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

fail() {
  printf 'sanitize-check failed: %s\n' "$*" >&2
  exit 1
}

tracked_sensitive="$(git ls-files \
  '.env' '*.env' '*.key' '*secret*' 'auth.json' 'credentials*' 'config.json' \
  'agent_queue/**' 'agent_tasks/**' 'agent_sessions/**' 'worktrees/**' 'worktree_archives/**' \
  '__pycache__/**' '*.pyc' 2>/dev/null || true)"
if [[ -n "$tracked_sensitive" ]]; then
  printf '%s\n' "$tracked_sensitive" >&2
  fail "tracked runtime, cache, or sensitive-looking files are present"
fi

found_runtime="$(find . \
  -path './.git' -prune -o \
  \( -name '__pycache__' -o -name '*.pyc' -o -name 'config.json' -o -name '.env' -o -name '*.key' -o -name 'auth.json' -o -name 'credentials*' \) \
  -print)"
if [[ -n "$found_runtime" ]]; then
  printf '%s\n' "$found_runtime" >&2
  fail "runtime, cache, or sensitive-looking files exist in the working tree"
fi

if rg -n --hidden --glob '!.git/**' \
  '(sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY|access_key=[A-Za-z0-9._-]{16,}|refresh_token["'\'']?\s*[:=]\s*["'\''][A-Za-z0-9._-]{20,})' \
  .; then
  fail "high-signal secret pattern matched"
fi

if rg -n --hidden --glob '!.git/**' --glob '!tests/**' --glob '!scripts/sanitize-check.sh' \
  '/root/|/mnt/[a-zA-Z]/|data-agent|hermes-write-smoke' .; then
  fail "local machine path or private project marker matched outside tests"
fi

printf 'sanitize-check passed\n'
