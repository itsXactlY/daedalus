#!/usr/bin/env bash
# BTQuant Agency Loop — pre-flight verification
# Run this BEFORE starting the perpetual loop to catch the common
# failure modes documented in references/agency-loop-bringup.md.

set -u  # don't `set -e` — we want to report ALL problems, not bail on first

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { printf "  ${GREEN}OK${NC}    %s\n" "$1"; }
warn() { printf "  ${YELLOW}WARN${NC}  %s\n" "$1"; }
fail() { printf "  ${RED}FAIL${NC}  %s\n" "$1"; }

BTQ_DIR="${BTQ_DIR:-$HOME/projects/PubBTQuant}"
GATEWAY_URL="${GATEWAY_URL:-https://localhost:8443/v1}"

cd "$BTQ_DIR" 2>/dev/null || { fail "BTQ dir not found: $BTQ_DIR"; exit 1; }
ok "BTQ_DIR = $BTQ_DIR"

echo
echo "--- 1. Gateway (Hermes LAN) ---"
if curl -sk -m 5 "$GATEWAY_URL/models" 2>/dev/null | grep -q wonderland; then
    ok "Gateway reachable at $GATEWAY_URL"
else
    fail "Gateway unreachable at $GATEWAY_URL"
    echo "       Try: systemctl --user status mazemaker-apk-gateway"
fi

echo
echo "--- 2. Gateway upstream wired ---"
RESP=$(curl -sk -m 30 -X POST "$GATEWAY_URL/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"wonderland","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' 2>&1)
if echo "$RESP" | grep -q '"content"'; then
    ok "Upstream reachable, real LLM traffic"
elif echo "$RESP" | grep -q 'rate_limit_error'; then
    warn "Upstream MiniMax at quota (Token Plan 2056). Loop will use fallback."
elif echo "$RESP" | grep -q 'upstream is not configured'; then
    fail "Gateway has no upstream configured. See references/hermes-llm-gateway.md"
    echo "       Fix: add EnvironmentFile=.../container/gateway.env to the systemd unit"
else
    warn "Unexpected response: $(echo "$RESP" | head -c 200)"
fi

echo
echo "--- 3. Parquet cache ---"
PARQUET=$(find .btq_cache -name "*.parquet" 2>/dev/null | head -1)
if [ -n "$PARQUET" ]; then
    ROWS=$(python3 -c "import pandas as pd; print(len(pd.read_parquet('$PARQUET')))" 2>/dev/null)
    ok "Parquet: $PARQUET ($ROWS rows)"
else
    fail "No parquet in .btq_cache/. Run: python3 mock_data_producer.py &"
fi

echo
echo "--- 4. Python packages ---"
MISSING=$(python3 -c "
import importlib
missing = []
for m in ['aiohttp','psutil','apscheduler','pandas','numpy','backtrader',
         'quantstats_lumi','reportlab','markdown','pdfkit']:
    try:
        importlib.import_module(m)
    except ImportError:
        missing.append(m)
print(' '.join(missing))
")
if [ -z "$MISSING" ]; then
    ok "all packages present"
else
    fail "missing: $MISSING"
    echo "       Fix: pip install --break-system-packages $MISSING"
fi

echo
echo "--- 5. Git state ---"
if git status 2>&1 | grep -q "Revert zurzeit im Gange"; then
    fail "Git revert is in progress! Patches to existing files are being wiped."
    echo "       Fix: git revert --abort && re-apply patches"
elif git status 2>&1 | grep -q "neue Dateien\|Untracked files"; then
    ok "Working tree OK (untracked new files are expected)"
else
    ok "Working tree clean"
fi

echo
echo "--- 6. Loop module importable ---"
if python3 -c "from autonomous_agency.perpetual_loop import PerpetualLoop; print('OK')" 2>&1 | grep -q "^OK$"; then
    ok "autonomous_agency.perpetual_loop imports clean"
else
    fail "perpetual_loop import broken"
fi

echo
echo "--- 7. SSL config ---"
if [ -n "${BTQ_LLM_INSECURE:-}" ]; then
    ok "BTQ_LLM_INSECURE=$BTQ_LLM_INSECURE"
else
    warn "BTQ_LLM_INSECURE not set — required for self-signed gateway cert"
    echo "       Set: export BTQ_LLM_INSECURE=1"
fi

echo
echo "--- summary ---"
echo "If everything above is OK or WARN, run:"
echo "  cd $BTQ_DIR && BTQ_LLM_INSECURE=1 python3 -m autonomous_agency.run_loop --interval 30 --hypotheses 8"
