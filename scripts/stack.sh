#!/usr/bin/env bash
# Deprecated shim. The local inference stack now lives inside the CLI:
#
#   daedalus doctor              what is present, what is missing, what is running
#   daedalus doctor setup        clone + build llama.cpp, fetch the models
#   daedalus doctor start        bring the inference servers up
#   daedalus doctor stop         take them down
#   daedalus doctor restart
#   daedalus doctor pause        freeze them, keep the weights loaded
#   daedalus doctor resume
#   daedalus doctor status       ports, pids, VRAM
#   daedalus doctor logs [main|aux|vis]
#   daedalus doctor conf         where the knobs live
#
# It is the same lifecycle, the same $DAEDALUS_HOME/stack.conf and the same pid
# files — implemented in daedalus_cli/stack.py rather than here, so the command
# that reports on the servers is also the command that runs them.
#
# This file forwards, so anything that already calls it keeps working.
set -uo pipefail

DAEDALUS="${DAEDALUS_BIN:-daedalus}"
if ! command -v "$DAEDALUS" >/dev/null 2>&1; then
  echo "stack.sh: '$DAEDALUS' is not on PATH — install it with ./install.sh," >&2
  echo "          or set DAEDALUS_BIN to the daedalus executable." >&2
  exit 127
fi

case "${1:-}" in
  # `stack.sh doctor` reported only the stack; the bare `daedalus doctor` now
  # reports everything, so the stack-only view keeps its own name.
  doctor)  shift; exec "$DAEDALUS" doctor stack "$@" ;;
  setup)   shift; exec "$DAEDALUS" doctor setup "$@" ;;
  start)   shift; exec "$DAEDALUS" doctor start "$@" ;;
  stop)    shift; exec "$DAEDALUS" doctor stop "$@" ;;
  restart) shift; exec "$DAEDALUS" doctor restart "$@" ;;
  pause)   shift; exec "$DAEDALUS" doctor pause "$@" ;;
  resume)  shift; exec "$DAEDALUS" doctor resume "$@" ;;
  status)  shift; exec "$DAEDALUS" doctor status "$@" ;;
  logs)    shift; exec "$DAEDALUS" doctor logs "$@" ;;
  conf)    shift; exec "$DAEDALUS" doctor conf "$@" ;;
  ""|-h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) echo "unknown command: $1" >&2; exit 2 ;;
esac
