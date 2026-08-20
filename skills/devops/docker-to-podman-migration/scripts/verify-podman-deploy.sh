#!/usr/bin/env bash
# Verify a Docker→Podman migration produced a correct, single amd64 pod.
# Usage: verify-podman-deploy.sh <compose_dir> <service_name> <port>
# Exit 0 on all checks passing; non-zero on first failure.
set -euo pipefail

COMPOSE_DIR="${1:?usage: verify-podman-deploy.sh <compose_dir> <service_name> <port>}"
SERVICE="${2:?service name required}"
PORT="${3:?port required}"

cd "$COMPOSE_DIR"

echo "=== 1. compose.yaml parses ==="
docker-compose config >/dev/null 2>&1 || { echo "FAIL: compose config invalid"; exit 1; }
echo "PASS: compose.yaml valid"

echo
echo "=== 2. build.platforms pinned to linux/amd64 ==="
if grep -q "linux/amd64" compose.yaml; then
  echo "PASS: platform pinned in compose"
else
  echo "WARN: platform not pinned in compose.yaml (must pass --platform at build)"
fi

echo
echo "=== 3. running image is amd64 ==="
img="localhost/${SERVICE}:local"
arch=$(podman inspect "$img" --format '{{.Architecture}} {{.Os}}' 2>/dev/null || echo "missing")
echo "image arch/os: $arch"
[[ "$arch" == "amd64 linux" ]] || { echo "FAIL: image not amd64 linux (got: $arch)"; exit 1; }

echo
echo "=== 4. exactly ONE container for the service ==="
ncont=$(podman ps -a --filter name="${SERVICE}" --format '{{.Names}}' | wc -l)
echo "containers named '${SERVICE}': $ncont"
[[ "$ncont" == "1" ]] || { echo "FAIL: expected 1 container, got $ncont (duplicates from --platform rebuilds)"; exit 1; }

echo
echo "=== 5. health endpoint responds ==="
body=$(curl -s "http://127.0.0.1:${PORT}/health" || true)
echo "health: $body"
[[ "$body" == *'"status": "ok"'* ]] || { echo "FAIL: health endpoint unhealthy"; exit 1; }

echo
echo "ALL CHECKS PASSED (amd64 single pod on port ${PORT})"
