#!/usr/bin/env bash
# Daedalus 0.8.1 installer — uv/uvx based.
#
# Usage:
#   ./install.sh              # install as a persistent uv tool  -> `daedalus`
#   ./install.sh --run        # one-shot ephemeral run, installs nothing
#   ./install.sh --dev        # editable install into a local .venv (for hacking)
#   ./install.sh --extras "messaging,cron,mcp"
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="tool"; EXTRAS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --run)    MODE="run" ;;
    --dev)    MODE="dev" ;;
    --extras) EXTRAS="${2:-}"; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if ! command -v uv >/dev/null 2>&1; then
  echo "==> uv not found; installing (https://astral.sh/uv)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv lands in ~/.local/bin (or $XDG_BIN_HOME); make it visible to THIS shell.
  export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
  command -v uv >/dev/null 2>&1 || { echo "uv still not on PATH; open a new shell and re-run" >&2; exit 1; }
fi

TARGET="$HERE"
[ -n "$EXTRAS" ] && TARGET="${HERE}[${EXTRAS}]"

case "$MODE" in
  run)
    echo "==> ephemeral run (nothing installed)"
    exec uvx --from "$TARGET" daedalus
    ;;
  dev)
    echo "==> editable install into $HERE/.venv"
    uv venv --python 3.14 "$HERE/.venv"
    VIRTUAL_ENV="$HERE/.venv" uv pip install -e "$TARGET"
    echo "==> done. activate with:  source $HERE/.venv/bin/activate"
    ;;
  tool)
    echo "==> installing as a uv tool"
    uv tool install --force --from "$TARGET" daedalus
    echo
    echo "==> installed. If 'daedalus' is not found, run:  uv tool update-shell"
    ;;
esac

cat <<'NEXT'

Next steps
----------
  1. daedalus setup          # interactive first-run configuration
  2. Put your API keys in the environment or in ~/.daedalus/.env
     (copy .env.example as a starting point — never commit the result)
  3. daedalus                # start the interactive agent

Config lives in ~/.daedalus/ by default. Point elsewhere with DAEDALUS_HOME.
To reuse an existing upstream Daedalus home:  DAEDALUS_HOME=~/.daedalus daedalus
NEXT
