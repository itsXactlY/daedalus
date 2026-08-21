#!/usr/bin/env python3
"""Ollama-compat proxy -> llama.cpp OpenAI-compat backend.

The pulse-pro Pod (FastAPI :8770) speaks ONLY Ollama protocol
(/api/tags, /api/generate). llama.cpp speaks OpenAI-compat
(/v1/chat/completions). This proxy translates so the Pod can use a local
llama.cpp model WITHOUT a Pod rebuild.

Run:  python3 ollama-compat-proxy.py
Listens on :11435 by default (override with PROXY_PORT env).

Then point the Pod's quadlet at it:
  Environment=OLLAMA_BASE_URL=http://host.containers.internal:11435
  Environment=OLLAMA_MODEL=<exact model name from /v1/models>
"""
import json
import urllib.request
import http.server
import socketserver
import os

LLAMA_BASE = os.environ.get("LLAMA_BASE_URL", "http://127.0.0.1:8080")
LLAMA_KEY = os.environ.get("LLAMA_KEY", "sk-llama")
LISTEN_PORT = int(os.environ.get("PROXY_PORT", "11435"))


def llama_model_name() -> str:
    try:
        with urllib.request.urlopen(f"{LLAMA_BASE}/v1/models", timeout=5) as r:
            d = json.loads(r.read().decode())
        models = d.get("models") or []
        if models:
            return models[0].get("id") or models[0].get("name")
    except Exception:
        pass
    return "local"


MODEL = llama_model_name()


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("/api/tags", "/api/tags/"):
            self._send(200, {"models": [{"name": MODEL, "model": MODEL,
                                          "details": {"family": "llama.cpp"},
                                          "size": 0}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") not in ("/api/generate", "/api/generate/"):
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length).decode() or "{}")
        prompt = req.get("prompt", "")
        messages = [{"role": "user", "content": prompt}]
        payload = {
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "temperature": float(req.get("options", {}).get("temperature", 0.0)),
            "max_tokens": int(req.get("options", {}).get("num_predict", 512)),
        }
        try:
            r = urllib.request.Request(
                f"{LLAMA_BASE}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json",
                          "Authorization": f"Bearer {LLAMA_KEY}"},
                method="POST",
            )
            with urllib.request.urlopen(r, timeout=120) as resp:
                out = json.loads(resp.read().decode())
            text = out["choices"][0]["message"]["content"]
        except Exception:
            text = ""
        self._send(200, {"model": MODEL, "response": text, "done": True})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"[proxy] Ollama-compat -> {LLAMA_BASE} (model={MODEL}) on :{LISTEN_PORT}")
    with socketserver.TCPServer(("0.0.0.0", LISTEN_PORT), Handler) as httpd:
        httpd.serve_forever()
