#!/usr/bin/env python3
"""
MCP JSON-RPC fallback helper for the mazemaker pod.

When the Hermes MCP client reports "MCP server 'mazemaker' is unreachable
after N consecutive failures" but the pod is actually healthy, call the
JSON-RPC endpoint directly. Verified live 2026-06-18 against
http://127.0.0.1:8765/mcp (206k memories, dream engine live).

Usage from execute_code:
    Paste the helpers inline (this script is a template, not an importable module).

Or run directly:
    python3 scripts/mcp_jsonrpc_fallback.py health
    python3 scripts/mcp_jsonrpc_fallback.py recall "MCP CVEs" 5
"""
import json
import sys
import urllib.request

ENDPOINT = "http://127.0.0.1:8765/mcp"
TIMEOUT = 30


def mcp_call(method: str, params: dict, call_id: int = 1) -> dict:
    """Send one JSON-RPC 2.0 request to the MCP pod."""
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params, "id": call_id}
    ).encode()
    req = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def mcp_tool(name: str, arguments: dict):
    """Call an MCP tool by name. Returns parsed JSON or {"raw": text}."""
    res = mcp_call("tools/call", {"name": name, "arguments": arguments})
    if "result" in res and "content" in res["result"]:
        text = res["result"]["content"][0]["text"]
        try:
            return json.loads(text) if text.strip().startswith(("{", "[")) else {"raw": text}
        except json.JSONDecodeError:
            return {"raw": text}
    return res


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    tool = sys.argv[1]
    args = {}
    if tool == "health":
        args = {}
    elif tool in ("recall", "recall_advanced", "recall_multi"):
        args = {
            "query": sys.argv[2] if len(sys.argv) > 2 else "",
            "limit": int(sys.argv[3]) if len(sys.argv) > 3 else 5,
        }
    elif tool == "get":
        args = {"memory_id": int(sys.argv[2])}
    elif tool == "browse":
        args = {
            "limit": int(sys.argv[2]) if len(sys.argv) > 2 else 20,
            "label_prefix": sys.argv[3] if len(sys.argv) > 3 else "",
        }
    elif tool == "remember":
        print("remember needs --content and --label; use python from execute_code instead", file=sys.stderr)
        sys.exit(2)
    result = mcp_tool(tool, args)
    print(json.dumps(result, indent=2)[:4000])
