#!/bin/sh
# hermes-agent native-python launcher for the podroid Alpine rootfs.
# Placed at /opt/hermes/start.sh. Replaces the old `exec /opt/hermes/hermes-agent.bin`.
#
# Server side: gateway/config.py reads API_SERVER_* to enable the OpenAI-compatible
# api_server platform that HermesGatewayClient (Kotlin) talks to over SSE.
export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-8088}"
export API_SERVER_CORS_ORIGINS="${API_SERVER_CORS_ORIGINS:-*}"
export API_SERVER_KEY="${API_SERVER_KEY:-}"
export HERMES_HOME="${HERMES_HOME:-/opt/hermes/hermes-agent-data}"
export PYTHONUNBUFFERED=1
mkdir -p "$HERMES_HOME"

# Optional upstream LLM config (gateway-2 / Wonderland relay). When set, write
# ~/.hermes/config.yaml so the agent forwards completions to the real endpoint.
if [ -n "${HERMES_BASE_URL:-}" ]; then
    mkdir -p /root/.hermes
    cat > /root/.hermes/config.yaml <<YAML
default_model: ${HERMES_MODEL:-miniMax-m3}
profiles:
  default:
    base_url: ${HERMES_BASE_URL}
    api_key: ${HERMES_API_KEY:-sk-local}
YAML
fi

exec /opt/hermes/venv/bin/hermes gateway
