#!/usr/bin/env bash
# Daedalus local stack — fetch it, build it, run it.
#
#   ./scripts/stack.sh doctor     what is present, what is missing
#   ./scripts/stack.sh setup      clone + build llama.cpp, fetch the models
#   ./scripts/stack.sh start      bring both inference servers up
#   ./scripts/stack.sh stop       take them down
#   ./scripts/stack.sh restart
#   ./scripts/stack.sh pause      freeze them, keep the weights loaded
#   ./scripts/stack.sh resume
#   ./scripts/stack.sh status     ports, pids, VRAM
#   ./scripts/stack.sh logs [main|aux]
#
# Everything is driven by $DAEDALUS_HOME/stack.conf, written on first setup.
# Edit it rather than this script.
set -uo pipefail

DAEDALUS_HOME="${DAEDALUS_HOME:-$HOME/.daedalus}"
CONF="$DAEDALUS_HOME/stack.conf"
RUN_DIR="$DAEDALUS_HOME/run"
LOG_DIR="$DAEDALUS_HOME/logs"

B=$'\033[1m'; DIM=$'\033[2m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; N=$'\033[0m'
say()  { printf '%s\n' "$*"; }
ok()   { printf "  ${GRN}✓${N} %s\n" "$*"; }
warn() { printf "  ${YEL}!${N} %s\n" "$*"; }
bad()  { printf "  ${RED}✗${N} %s\n" "$*"; }
head_() { printf "\n${B}%s${N}\n" "$*"; }

write_default_conf() {
  mkdir -p "$DAEDALUS_HOME"
  cat > "$CONF" <<'CONF_EOF'
# Daedalus local stack. Paths are absolute; ~ is expanded on load.

# --- where the llama.cpp fork lives and gets built ---------------------------
# Adaptive KV streaming keeps the KV cache in pinned host memory, which is what
# lets a 27B model hold a six-figure context on a 16 GB card.
LLAMA_DIR="$HOME/projects/llama.cpp-adaptive-kv-streaming"
LLAMA_REPO="https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming"
LLAMA_BRANCH="feature/adaptive-kv-stream"

# --- main model --------------------------------------------------------------
MAIN_REPO="ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF"
MAIN_FILE="Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
MAIN_PORT=8080
MAIN_HOST="127.0.0.1"
MAIN_CTX=131072
# Resident KV pool in VRAM, MiB. Raise it while watching peak VRAM; the rest of
# the cache streams from host memory.
MAIN_KV_POOL=2048
MAIN_NGL=99
MAIN_THREADS=8
MAIN_REASONING_BUDGET=12000
# Optional vision projector. Leave empty to run without vision.
MMPROJ=""

# --- auxiliary model ---------------------------------------------------------
# Small, CPU-only, on its own port so background work never queues behind the
# main model. -ngl 0 is deliberate: it costs no VRAM and runs truly in parallel.
AUX_REPO="enacimie/Qwen3-1.7B-Q4_K_M-GGUF"
AUX_FILE="qwen3-1.7b-q4_k_m.gguf"
AUX_PORT=8081
AUX_HOST="127.0.0.1"
AUX_CTX=12096
AUX_THREADS=6
AUX_ENABLED=1
CONF_EOF
}

load_conf() {
  [ -f "$CONF" ] || write_default_conf
  # shellcheck disable=SC1090
  . "$CONF"
  LLAMA_DIR="${LLAMA_DIR/#\~/$HOME}"
  MMPROJ="${MMPROJ/#\~/$HOME}"
  SERVER="$LLAMA_DIR/build/bin/llama-server"
  mkdir -p "$RUN_DIR" "$LOG_DIR"
}

model_path() {  # repo, file -> resolved gguf path or empty
  local repo="$1" file="$2" dir
  dir="$HOME/.cache/huggingface/hub/models--${repo//\//--}"
  [ -d "$dir" ] || return 0
  # Snapshot entries are symlinks into blobs/, so -type f misses every one.
  find -L "$dir" -name "$file" 2>/dev/null | head -1
}

pid_of() { local n="$1"; [ -f "$RUN_DIR/$n.pid" ] && cat "$RUN_DIR/$n.pid" || true; }
alive()  { local p="$1"; [ -n "$p" ] && kill -0 "$p" 2>/dev/null; }
port_up() { timeout 2 curl -sf -o /dev/null "http://$1:$2/health" 2>/dev/null; }

state_of() {  # name host port -> running|paused|stopped
  local p; p="$(pid_of "$1")"
  alive "$p" || { echo stopped; return; }
  case "$(ps -o state= -p "$p" 2>/dev/null | tr -d ' ')" in
    T*) echo paused ;;
    *)  echo running ;;
  esac
}

# ---------------------------------------------------------------- doctor -----
cmd_doctor() {
  head_ "Toolchain"
  for c in git cmake curl; do
    command -v "$c" >/dev/null && ok "$c" || bad "$c — required"
  done
  command -v hf >/dev/null && ok "hf (huggingface CLI)" \
    || warn "hf missing — pip install huggingface_hub[cli]"
  if command -v nvcc >/dev/null; then ok "nvcc $(nvcc --version | tail -1 | grep -o 'cuda_[0-9.]*')"
  else warn "nvcc missing — the CUDA build needs the toolkit, not just the driver"; fi
  command -v nvidia-smi >/dev/null && ok "nvidia-smi" || warn "no nvidia-smi — CPU only"

  head_ "Sources"
  [ -d "$LLAMA_DIR/.git" ] && ok "llama.cpp at $LLAMA_DIR" || bad "llama.cpp missing — run: $0 setup"
  [ -x "$SERVER" ] && ok "llama-server built" || bad "llama-server not built — run: $0 setup"

  head_ "Models"
  local m a
  m="$(model_path "$MAIN_REPO" "$MAIN_FILE")"
  a="$(model_path "$AUX_REPO" "$AUX_FILE")"
  [ -n "$m" ] && ok "main: $(basename "$m") ($(du -hL "$m" | cut -f1))" || bad "main model missing — run: $0 setup"
  if [ "${AUX_ENABLED:-1}" = "1" ]; then
    [ -n "$a" ] && ok "aux:  $(basename "$a") ($(du -hL "$a" | cut -f1))" || bad "aux model missing — run: $0 setup"
  fi
  [ -n "$MMPROJ" ] && { [ -f "$MMPROJ" ] && ok "mmproj: $MMPROJ" || warn "MMPROJ set but not found: $MMPROJ"; }

  head_ "Memory backend"
  local url="${MM_WONDERLAND_URL:-http://127.0.0.1:8765}"
  # The pod speaks MCP, not a plain health route, so probe the socket rather
  # than guessing a path — a GET on / hangs waiting for a session.
  local mm_host mm_port
  mm_host="$(printf '%s' "$url" | sed -E 's#^https?://##; s#[:/].*$##')"
  mm_port="$(printf '%s' "$url" | sed -nE 's#^https?://[^:/]+:([0-9]+).*#\1#p')"
  mm_port="${mm_port:-8765}"
  if timeout 3 bash -c "exec 3<>/dev/tcp/$mm_host/$mm_port" 2>/dev/null; then
    ok "mazemaker listening on $mm_host:$mm_port"
  else
    bad "mazemaker NOT reachable at $url"
    say "    Without it this harness is an amnesiac: it stops carrying its own"
    say "    history by design. See https://mazemaker.online"
  fi

  head_ "Servers"
  cmd_status
}

# ----------------------------------------------------------------- setup -----
cmd_setup() {
  head_ "llama.cpp (adaptive KV streaming)"
  if [ ! -d "$LLAMA_DIR/.git" ]; then
    mkdir -p "$(dirname "$LLAMA_DIR")"
    git clone --branch "$LLAMA_BRANCH" "$LLAMA_REPO" "$LLAMA_DIR" || return 1
  else
    ok "already cloned"
  fi
  if [ ! -x "$SERVER" ]; then
    say "  building (this takes a while)…"
    cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" \
          -DGGML_CUDA=ON -DGGML_CUDA_FA_ALL_QUANTS=ON -DCMAKE_BUILD_TYPE=Release \
      && cmake --build "$LLAMA_DIR/build" --config Release --target llama-server -j \
      || { bad "build failed"; return 1; }
  fi
  ok "llama-server ready"

  head_ "Models"
  command -v hf >/dev/null || { bad "hf CLI missing"; return 1; }
  [ -n "$(model_path "$MAIN_REPO" "$MAIN_FILE")" ] \
    && ok "main present" || hf download "$MAIN_REPO" "$MAIN_FILE" || return 1
  if [ "${AUX_ENABLED:-1}" = "1" ]; then
    [ -n "$(model_path "$AUX_REPO" "$AUX_FILE")" ] \
      && ok "aux present" || hf download "$AUX_REPO" "$AUX_FILE" || return 1
  fi
  say ""
  ok "setup complete — $0 start"
}

# ----------------------------------------------------------------- start -----
start_one() {  # name, then argv
  local name="$1"; shift
  local st; st="$(state_of "$name")"
  if [ "$st" != stopped ]; then warn "$name already $st"; return 0; fi
  ( setsid nohup "$@" > "$LOG_DIR/$name.log" 2>&1 < /dev/null & echo $! > "$RUN_DIR/$name.pid" )
  say "  ${DIM}$name starting…${N}"
}

wait_ready() {  # name host port seconds
  local name="$1" host="$2" port="$3" secs="${4:-180}" i=0
  while [ "$i" -lt "$secs" ]; do
    port_up "$host" "$port" && { ok "$name up on $host:$port"; return 0; }
    alive "$(pid_of "$name")" || { bad "$name died — $0 logs $name"; return 1; }
    sleep 2; i=$((i+2))
  done
  bad "$name did not answer within ${secs}s — $0 logs $name"; return 1
}

cmd_start() {
  local main aux
  main="$(model_path "$MAIN_REPO" "$MAIN_FILE")"
  [ -x "$SERVER" ] || { bad "llama-server not built — run: $0 setup"; return 1; }
  [ -n "$main" ]   || { bad "main model missing — run: $0 setup"; return 1; }

  head_ "Starting"
  local -a m=("$SERVER" --model "$main"
      --host "$MAIN_HOST" --port "$MAIN_PORT"
      --ctx-size "$MAIN_CTX" --kv-stream-stage-mib "$MAIN_KV_POOL"
      -ctk q4_0 -ctv q4_0 -fa on -ngl "$MAIN_NGL" -t "$MAIN_THREADS" -np 1
      -b 512 -ub 512
      --temp 1.0 --top-k 20 --min-p 0.00 --top-p 0.95
      --presence-penalty 0.0 --repeat-penalty 1.0
      --reasoning on --reasoning-preserve --reasoning-format deepseek
      --reasoning-budget "$MAIN_REASONING_BUDGET"
      --spec-type draft-mtp,ngram-mod --spec-draft-n-max 2
      --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 24 --spec-ngram-mod-n-max 32
      --jinja --cont-batching)
  if [ -n "$MMPROJ" ] && [ -f "$MMPROJ" ]; then
    m+=(-mm "$MMPROJ" --no-mmproj-offload --image-min-tokens 1024 --image-max-tokens 2048)
  fi
  start_one main "${m[@]}"

  # The main model must be READY before the helper starts. Both loading at once
  # means two processes fighting for RAM while the big one is pinning 9 GB of
  # KV cache: the machine swaps, and anything else on it (a memory pod running
  # consolidation, for one) stalls behind the page-outs.
  wait_ready main "$MAIN_HOST" "$MAIN_PORT" 300 || return 1

  if [ "${AUX_ENABLED:-1}" = "1" ]; then
    aux="$(model_path "$AUX_REPO" "$AUX_FILE")"
    if [ -n "$aux" ]; then
      # --reasoning off is load-bearing: with thinking on, a 1.7B spends its
      # whole output budget reasoning and returns empty content.
      start_one aux "$SERVER" --model "$aux" \
        --host "$AUX_HOST" --port "$AUX_PORT" \
        --ctx-size "$AUX_CTX" -ngl 0 -t "$AUX_THREADS" -np 2 \
        -b 512 -ub 512 --cont-batching --jinja \
        --temp 0.3 --top-p 0.9 --reasoning off
    else
      warn "aux model missing — skipping"
    fi
  fi

  [ "${AUX_ENABLED:-1}" = "1" ] && [ -n "${aux:-}" ] && wait_ready aux "$AUX_HOST" "$AUX_PORT" 180
  return 0
}

# ------------------------------------------------------------------ stop -----
stop_one() {
  local name="$1" p; p="$(pid_of "$name")"
  if ! alive "$p"; then rm -f "$RUN_DIR/$name.pid"; return 0; fi
  kill -CONT "$p" 2>/dev/null
  kill -TERM "$p" 2>/dev/null
  local i=0
  while alive "$p" && [ "$i" -lt 20 ]; do sleep 0.5; i=$((i+1)); done
  alive "$p" && kill -KILL "$p" 2>/dev/null
  rm -f "$RUN_DIR/$name.pid"
  ok "$name stopped"
}

cmd_stop()    { head_ "Stopping"; stop_one aux; stop_one main; }
cmd_restart() { cmd_stop; cmd_start; }

signal_all() {  # signal, verb
  local sig="$1" verb="$2" n p any=0
  head_ "$verb"
  for n in main aux; do
    p="$(pid_of "$n")"
    alive "$p" && { kill "-$sig" "$p" 2>/dev/null && ok "$n $verb"; any=1; }
  done
  [ "$any" = 0 ] && warn "nothing running"
  return 0
}

cmd_pause()  { signal_all STOP paused; say "  ${DIM}weights stay loaded; resume with: $0 resume${N}"; }
cmd_resume() { signal_all CONT resumed; }

# ---------------------------------------------------------------- status -----
cmd_status() {
  local n host port st p
  for n in main aux; do
    case "$n" in
      main) host="$MAIN_HOST"; port="$MAIN_PORT" ;;
      aux)  host="$AUX_HOST";  port="$AUX_PORT"  ;;
    esac
    st="$(state_of "$n")"; p="$(pid_of "$n")"
    case "$st" in
      running) port_up "$host" "$port" && ok "$n  $host:$port  pid $p" \
                                       || warn "$n  pid $p — process up, port not answering yet" ;;
      paused)  warn "$n  pid $p — paused" ;;
      *)
        # A server this script did not start still occupies the port. Saying
        # "stopped" while something answers there is worse than saying nothing.
        if port_up "$host" "$port"; then
          warn "$n  $host:$port answering, but not started by this script (no pid file)"
        else
          say "  ${DIM}·${N} $n  stopped"
        fi ;;
    esac
  done
  if command -v nvidia-smi >/dev/null 2>&1; then
    say "  ${DIM}VRAM: $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader)${N}"
  fi
}

cmd_logs() { local n="${1:-main}"; tail -f "$LOG_DIR/$n.log"; }

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }

load_conf
case "${1:-}" in
  doctor)  cmd_doctor ;;
  setup)   cmd_setup ;;
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  pause)   cmd_pause ;;
  resume)  cmd_resume ;;
  status)  head_ "Servers"; cmd_status ;;
  logs)    cmd_logs "${2:-main}" ;;
  ""|-h|--help) usage ;;
  *) echo "unknown command: $1" >&2; usage; exit 2 ;;
esac
