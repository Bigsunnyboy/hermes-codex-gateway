#!/usr/bin/env bash
set -euo pipefail

IMAGE="${HERMES_DOCKER_IMAGE:-nousresearch/hermes-agent:latest}"
PLUGIN_SOURCE="${1:-}"

if [[ -z "$PLUGIN_SOURCE" ]]; then
  PLUGIN_SOURCE="$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." config --get remote.origin.url || true)"
fi

if [[ -z "$PLUGIN_SOURCE" ]]; then
  echo "usage: scripts/docker-official-smoke.sh <git-url-or-file-url>" >&2
  echo "or configure git remote origin for this repository" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workdir="$(mktemp -d)"
cleanup() {
  rm -rf "$workdir"
}
trap cleanup EXIT

docker_args=(
  --rm
  -v "$workdir/data:/opt/data"
)

install_source="$PLUGIN_SOURCE"
if [[ "$PLUGIN_SOURCE" == "$repo_root" || "$PLUGIN_SOURCE" == "file://$repo_root" ]]; then
  docker_args+=(-v "$repo_root:/plugin-src:ro")
  install_source="file:///plugin-src"
fi

echo "Using image: $IMAGE"
echo "Using plugin source: $install_source"

docker run "${docker_args[@]}" "$IMAGE" \
  plugins install "$install_source" --enable

docker run "${docker_args[@]}" "$IMAGE" \
  plugins list | tee "$workdir/plugins-list.txt"

grep -q "hermes-codex-gateway" "$workdir/plugins-list.txt"
grep -qi "enabled" "$workdir/plugins-list.txt"

docker run "${docker_args[@]}" "$IMAGE" \
  bash -lc '
set -euo pipefail
python - <<'"'"'PY'"'"'
from hermes_cli.plugins import discover_plugins, get_plugin_manager
from tools.registry import registry

discover_plugins(force=True)
manager = get_plugin_manager()
plugin = manager._plugins.get("hermes-codex-gateway")
assert plugin is not None, "plugin was not discovered"
assert plugin.enabled, f"plugin not enabled: {plugin.error!r}"
assert plugin.error is None, plugin.error

expected_tools = {
    "submit_codex_command",
    "run_next_codex_task",
    "get_codex_task_status",
    "approve_codex_task",
    "manage_codex_workspace",
}
registered = set(plugin.tools_registered)
missing = expected_tools - registered
assert not missing, f"missing tools: {sorted(missing)}"

for name in expected_tools:
    assert registry.get_entry(name) is not None, f"tool not in registry: {name}"

assert "pre_gateway_dispatch" in plugin.hooks_registered

print("plugin_discovered=1")
print("plugin_enabled=1")
print("tools_registered=" + ",".join(sorted(registered)))
print("hooks_registered=" + ",".join(sorted(plugin.hooks_registered)))
PY
'

echo "docker-official-smoke passed"
