#!/usr/bin/env python3
"""OpenAI-compatible shim in front of the Claude Code CLI.

Daedalus already speaks ``POST /v1/chat/completions`` against an arbitrary
``base_url`` -- that is how it talks to any local inference server. So the
smallest possible Claude Code backend is not a code change inside the agent at
all: it is a process that speaks that endpoint and shells out to ``claude -p``.

    Daedalus ──HTTP──> this shim ──subprocess──> claude -p ──OAuth──> Claude

Point Daedalus at it and change nothing else:

    providers:
      claude:
        base_url: http://127.0.0.1:8790/v1
        api_key: not-used

Why a shim rather than a provider class: the agent has no pluggable provider
interface. It branches on ``api_mode`` in 67 places across three values. Adding
a fourth would mean touching all of them. This touches none.

No API key is involved anywhere. Claude Code owns authentication; if you are
logged in there, this works, and if you are not, it fails there rather than here.

Stdlib only, deliberately. A transport shim that drags in a web framework has
already failed at being minimal.

Usage:
    python3 claude_code_shim.py [--port 8790] [--model sonnet] [--timeout 600]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Claude Code inherits the invoking user's whole environment by default: every
# tool, MCP server and slash command configured in ~/.claude. For a transport
# that is contamination -- the agent supplies its own tools and expects the
# model to do nothing but answer. These flags reduce it to a completion
# endpoint. Verified: with them the init event reports tools [], mcp_servers []
# and 0 slash commands.
ISOLATION_FLAGS = [
    "--exclude-dynamic-system-prompt-sections",
    "--tools", "",
    "--disable-slash-commands",
    "--strict-mcp-config",
]

# Advertised context window. Daedalus asks /v1/models for this and sizes its
# compaction threshold from the answer, so a wrong number here makes it compact
# at the wrong point -- reporting 200K for a 1M model means throwing away 800K
# of usable context and paying to rebuild it.
#
# Seeded from the published windows, then corrected at runtime: every completion
# reports the real window in modelUsage[...].contextWindow, so the first call on
# a model replaces the guess with the truth.
DEFAULT_CONTEXT = 200000
SEED_CONTEXT = {
    "sonnet": 1000000, "opus": 1000000, "fable": 1000000, "mythos": 1000000,
    "haiku": 200000,
}


def _seed_context_for(name):
    n = (name or "").lower()
    for key, val in SEED_CONTEXT.items():
        if key in n:
            return val
    return DEFAULT_CONTEXT


def _learn_context(server, result_obj):
    """Record the real context window the CLI reports for each model."""
    for mid, stats in ((result_obj or {}).get("modelUsage") or {}).items():
        cw = stats.get("contextWindow")
        if isinstance(cw, int) and cw > 0:
            server.learned_ctx[mid] = cw

TOOL_PROTOCOL = (
    "\n\n# Tool use\n"
    "You have the following tools. To call one, emit a block of exactly this "
    "form and nothing else after it:\n"
    "<tool_call>\n{\"name\": \"<tool_name>\", \"arguments\": {...}}\n</tool_call>\n"
    "Emit ONE call and then STOP. Do not write anything after the call: you "
    "will be given the real result and asked again. Never invent a result. "
"If no tool is needed, answer normally.\n\nTools:\n"
)


def _render_messages(messages):
    """Split OpenAI messages into (system_prompt, transcript).

    Claude Code takes one prompt string, so history is rendered into it. That is
    correct here rather than lossy: Daedalus owns conversation state and resends
    the full message list every turn, so there is nothing for the CLI to
    remember between calls.
    """
    system_parts, lines = [], []
    for m in messages or []:
        role = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, list):  # multimodal blocks -> take the text parts
            content = "".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        content = content or ""
        if role in ("system", "developer"):
            if content.strip():
                system_parts.append(content)
        elif role == "tool":
            name = m.get("name") or m.get("tool_call_id") or "tool"
            lines.append(f"<tool_result name=\"{name}\">\n{content}\n</tool_result>")
        elif role == "assistant":
            calls = m.get("tool_calls") or []
            if calls:
                for c in calls:
                    fn = (c.get("function") or {})
                    lines.append(
                        "<tool_call>\n"
                        + json.dumps({"name": fn.get("name"),
                                      "arguments": fn.get("arguments")})
                        + "\n</tool_call>"
                    )
            if content.strip():
                lines.append(f"Assistant: {content}")
        else:
            lines.append(f"User: {content}")
    return "\n\n".join(system_parts), "\n\n".join(lines)


def _build_argv(body, default_model, claude_bin, stream):
    system_prompt, transcript = _render_messages(body.get("messages"))

    # Tool schemas go into the prompt, not into Claude Code. With --tools ""
    # the CLI will not execute anything and will not emit native tool_use
    # blocks, so the model is asked to emit calls as text and the agent's own
    # tool_call_parsers pick them up -- the same path its local models use.
    tools = body.get("tools") or []
    if tools:
        catalogue = []
        for t in tools:
            fn = t.get("function") or t
            catalogue.append(json.dumps({
                "name": fn.get("name"),
                "description": (fn.get("description") or "")[:400],
                "parameters": fn.get("parameters") or {},
            }))
        system_prompt = (system_prompt or "") + TOOL_PROTOCOL + "\n".join(catalogue)

    argv = [claude_bin, "-p", transcript or "(no input)"]
    argv += ["--output-format", "stream-json", "--include-partial-messages", "--verbose"] \
        if stream else ["--output-format", "json"]
    model = body.get("model") or default_model
    if model:
        argv += ["--model", model]
    if system_prompt.strip():
        argv += ["--system-prompt", system_prompt]
    argv += ISOLATION_FLAGS
    return argv


# The model improvises the wrapper tag. Across runs it has emitted
# <tool_call>, <call> and <function_calls> for the same instruction -- it is
# trained on native tool use, so a prompt-specified tag is a suggestion, not a
# contract. Matching a fixed tag therefore drops calls silently, which the agent
# sees as the model refusing to act. Match ANY tag wrapping a JSON object, and
# fall back to a bare object, then validate on shape instead of on syntax.
# A tagged block may hold one object or an array of them -- the model emits
# both shapes for the same instruction.
# Closing tags are not required to match the opening one: the model has been
# observed emitting "<call>{...}</tool_call>". Requiring a matched pair drops
# the call silently, which the agent experiences as the model refusing to act.
_TAGGED_RE = re.compile(r"<[A-Za-z_][\w.\-]*\s*>\s*([\[{].*?[\]}])\s*</[A-Za-z_][\w.\-]*\s*>", re.S)
_BARE_RE = re.compile(r"\{[^{}]*\"name\"\s*:.*?\}(?=\s*$|\s*\n)", re.S)
_EMPTY_TAG_RE = re.compile(r"<([A-Za-z_][\w.\-]*)\s*>\s*</\1\s*>", re.S)


def _as_call(obj):
    """Return an OpenAI tool_call for *obj*, or None if it is not one."""
    if not isinstance(obj, dict):
        return None
    name = obj.get("name") or obj.get("tool") or obj.get("tool_name")
    if not name or not isinstance(name, str):
        return None
    args = obj.get("arguments")
    if args is None:
        args = obj.get("parameters", obj.get("args", {}))
    if not isinstance(args, str):          # OpenAI carries arguments as a string
        args = json.dumps(args if args is not None else {}, ensure_ascii=False)
    return {"id": "call_" + uuid.uuid4().hex[:24], "type": "function",
            "function": {"name": name, "arguments": args}}


def _extract_tool_calls(text):
    """Lift tool calls out of the model's text into OpenAI shape.

    This has to happen here, not in the agent. Daedalus's tool_call_parsers are
    wired into environments/agent_loop.py only; run_agent.py -- the loop that
    actually runs the agent -- reads native ``message.tool_calls`` off the
    response and never inspects the text. Text-emitted calls are therefore
    printed to the user instead of executed.
    """
    text = text or ""
    calls, spans = [], []
    for m in _TAGGED_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        found = [c for c in map(_as_call, obj if isinstance(obj, list) else [obj]) if c]
        if found:
            calls.extend(found); spans.append(m.span())
    if not calls:
        for m in _BARE_RE.finditer(text):
            try:
                obj = json.loads(m.group(0))
            except Exception:
                continue
            c = _as_call(obj)
            if c:
                calls.append(c); spans.append(m.span())
    if not calls:
        return text.strip(), []
    # Keep only what came BEFORE the first call. Anything after it is the model
    # narrating results it never received -- it emits a call and then invents
    # the output, because it is trained to see real tool results at that point.
    # Passing that through would hand the agent fabricated data alongside a
    # genuine tool call.
    leftover = text[:spans[0][0]]
    # A wrapper tag opened just before the call leaves a dangling fragment.
    leftover = re.sub(r"<[A-Za-z_][\w.\-]*\s*>\s*$", "", leftover)
    # Outer wrappers (e.g. <function_calls> around the call) are now empty.
    prev = None
    while prev != leftover:
        prev = leftover
        leftover = _EMPTY_TAG_RE.sub("", leftover)
    return leftover.strip(), calls


def _usage(result_obj):
    """Map the CLI's accounting onto OpenAI usage.

    The CLI reports two views and they disagree. ``usage`` is the *billed*
    view; ``modelUsage`` is what the model actually read. Measured on one call:
    usage.input_tokens 2318 vs modelUsage.inputTokens 3217 -- ~900 tokens the
    billed view omits, with no cache involved.

    Reporting the billed view understates every turn, and Daedalus sizes
    compaction from these numbers, so understating them means compacting late
    and silently blowing the context window. It also makes a session's real
    token cost unauditable, which defeats the point of measuring it at all.

    So: prefer modelUsage, summed across every model that ran this turn (a
    refusal fallback or a router can involve more than one), and count cache
    reads and writes as prompt tokens because the model read them.
    """
    result_obj = result_obj or {}
    mu = result_obj.get("modelUsage") or {}
    if mu:
        read = sum(int(v.get("inputTokens") or 0) for v in mu.values())
        cache_r = sum(int(v.get("cacheReadInputTokens") or 0) for v in mu.values())
        cache_w = sum(int(v.get("cacheCreationInputTokens") or 0) for v in mu.values())
        out = sum(int(v.get("outputTokens") or 0) for v in mu.values())
    else:
        u = result_obj.get("usage") or {}
        read = int(u.get("input_tokens") or 0)
        cache_r = int(u.get("cache_read_input_tokens") or 0)
        cache_w = int(u.get("cache_creation_input_tokens") or 0)
        out = int(u.get("output_tokens") or 0)
    prompt = read + cache_r + cache_w
    usage = {
        "prompt_tokens": prompt,
        "completion_tokens": out,
        "total_tokens": prompt + out,
        "prompt_tokens_details": {"cached_tokens": cache_r},
    }
    # Non-standard, and deliberate: the CLI knows the actual dollar cost of the
    # turn. Passing it through makes a session's spend auditable instead of
    # estimated. Clients that do not know the field ignore it.
    cost = result_obj.get("total_cost_usd")
    if isinstance(cost, (int, float)):
        usage["total_cost_usd"] = cost
    return usage


_STOP_MAP = {"end_turn": "stop", "max_tokens": "length", "stop_sequence": "stop",
             "tool_use": "tool_calls", "refusal": "content_filter"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "claude-code-shim"

    # ---- plumbing --------------------------------------------------------
    def log_message(self, fmt, *a):
        if self.server.verbose:
            sys.stderr.write("  %s\n" % (fmt % a))

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _sse_open(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _sse(self, obj):
        self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
        self.wfile.flush()

    # ---- routes ----------------------------------------------------------
    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            now = int(time.time())
            learned = self.server.learned_ctx
            def ctx_for(alias):
                # A learned value for a full id (claude-sonnet-5) also answers
                # for its alias (sonnet), which is what the config usually says.
                for mid, cw in learned.items():
                    if alias in mid or mid in alias:
                        return cw
                return _seed_context_for(alias)
            models = [
                {"id": m, "object": "model", "created": now, "owned_by": "claude-code",
                 "context_length": ctx_for(m), "max_context_length": ctx_for(m),
                 "loaded": m == self.server.default_model}
                for m in ("sonnet", "opus", "fable", "haiku", self.server.default_model)
            ]
            seen, uniq = set(), []
            for m in models:
                if m["id"] and m["id"] not in seen:
                    seen.add(m["id"]); uniq.append(m)
            return self._json({"object": "list", "data": uniq})
        if self.path.rstrip("/").endswith("/health"):
            return self._json({"ok": True, "claude": self.server.claude_bin})
        return self._json({"error": {"message": "not found"}}, 404)

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json({"error": {"message": "not found"}}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:
            return self._json({"error": {"message": f"bad request: {exc}"}}, 400)

        stream = bool(body.get("stream"))
        argv = _build_argv(body, self.server.default_model, self.server.claude_bin, stream)
        cid = "chatcmpl-" + uuid.uuid4().hex[:24]
        created = int(time.time())
        model = body.get("model") or self.server.default_model or "claude"

        try:
            if stream:
                self._run_stream(argv, cid, created, model, bool(body.get("tools")))
            else:
                self._run_once(argv, cid, created, model)
        except subprocess.TimeoutExpired:
            self._fail(cid, created, model, stream, "claude timed out")
        except Exception as exc:
            self._fail(cid, created, model, stream, f"{type(exc).__name__}: {exc}")

    # ---- execution -------------------------------------------------------
    def _spawn(self, argv, stream):
        # stdin from DEVNULL is not optional: the CLI waits ~3s for piped input
        # and warns, adding that latency to every single call.
        return subprocess.Popen(
            argv, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1 if stream else -1,
            env={k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"},
        )

    def _run_once(self, argv, cid, created, model):
        p = self._spawn(argv, False)
        out, err = p.communicate(timeout=self.server.timeout)
        events = json.loads(out) if out.strip().startswith(("[", "{")) else []
        if isinstance(events, dict):
            events = [events]
        result = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if result is None:
            raise RuntimeError((err or out or "claude produced no result").strip()[:400])
        if result.get("is_error"):
            raise RuntimeError(str(result.get("result"))[:400])
        _learn_context(self.server, result)
        raw = result.get("result") or ""
        text, calls = _extract_tool_calls(raw)
        # An empty turn is the one failure the agent cannot recover from: it
        # renders as a blank answer with no error. Always record what the CLI
        # actually returned so the cause is visible instead of inferred.
        if not text and not calls:
            sys.stderr.write(
                "[shim] EMPTY TURN stop_reason=%r raw_len=%d raw=%r\n"
                % (result.get("stop_reason"), len(raw), raw[:600])
            )
            sys.stderr.flush()
        msg = {"role": "assistant", "content": text or None}
        finish = _STOP_MAP.get(result.get("stop_reason"), "stop")
        if calls:
            msg["tool_calls"] = calls
            finish = "tool_calls"
        self._json({
            "id": cid, "object": "chat.completion", "created": created, "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": _usage(result),
        })

    def _run_stream(self, argv, cid, created, model, has_tools=False):
        p = self._spawn(argv, True)
        self._sse_open()
        self._sse({"id": cid, "object": "chat.completion.chunk", "created": created,
                   "model": model,
                   "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]})
        result = None
        buffered = []
        for line in p.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") == "result":
                result = e
                continue
            if e.get("type") != "stream_event":
                continue
            ev = e.get("event") or {}
            if ev.get("type") != "content_block_delta":
                continue
            d = ev.get("delta") or {}
            # Thinking is surfaced as reasoning_content, which the agent already
            # consumes and stores separately from the answer.
            if d.get("type") == "text_delta" and d.get("text"):
                # When the turn may contain tool calls the answer text cannot be
                # streamed: a <tool_call> block has to be lifted out of the full
                # text and returned as structured tool_calls, and a fragment
                # already sent to the client cannot be taken back. Reasoning
                # still streams, so the turn stays visibly alive.
                if has_tools:
                    buffered.append(d["text"])
                    continue
                delta = {"content": d["text"]}
            elif d.get("type") == "thinking_delta" and d.get("thinking"):
                delta = {"reasoning_content": d["thinking"]}
            else:
                continue
            self._sse({"id": cid, "object": "chat.completion.chunk", "created": created,
                       "model": model,
                       "choices": [{"index": 0, "delta": delta, "finish_reason": None}]})
        p.wait(timeout=self.server.timeout)
        _learn_context(self.server, result)
        fin = _STOP_MAP.get((result or {}).get("stop_reason"), "stop")
        if has_tools:
            raw = "".join(buffered)
            text, calls = _extract_tool_calls(raw)
            if not text and not calls:
                sys.stderr.write(
                    "[shim] EMPTY TURN (stream) stop_reason=%r raw_len=%d raw=%r\n"
                    % ((result or {}).get("stop_reason"), len(raw), raw[:600])
                )
                sys.stderr.flush()
            if text:
                self._sse({"id": cid, "object": "chat.completion.chunk", "created": created,
                           "model": model,
                           "choices": [{"index": 0, "delta": {"content": text},
                                        "finish_reason": None}]})
            if calls:
                for i, c in enumerate(calls):
                    c = dict(c, index=i)
                    self._sse({"id": cid, "object": "chat.completion.chunk",
                               "created": created, "model": model,
                               "choices": [{"index": 0, "delta": {"tool_calls": [c]},
                                            "finish_reason": None}]})
                fin = "tool_calls"
        final = {"id": cid, "object": "chat.completion.chunk", "created": created,
                 "model": model,
                 "choices": [{"index": 0, "delta": {}, "finish_reason": fin}]}
        if result:
            final["usage"] = _usage(result)
        self._sse(final)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _fail(self, cid, created, model, stream, msg):
        if stream:
            try:
                self._sse({"id": cid, "object": "chat.completion.chunk", "created": created,
                           "model": model,
                           "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                           "error": {"message": msg}})
                self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
            except Exception:
                pass
        else:
            try:
                self._json({"error": {"message": msg, "type": "upstream_error"}}, 502)
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--model", default="sonnet", help="model used when the request omits one")
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per call")
    ap.add_argument("--claude", default=None, help="path to the claude executable")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    claude_bin = a.claude or shutil.which("claude")
    if not claude_bin:
        sys.exit("claude executable not found on PATH; pass --claude /path/to/claude")

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    srv.claude_bin = claude_bin
    srv.default_model = a.model
    srv.timeout = a.timeout
    srv.verbose = a.verbose
    srv.learned_ctx = {}
    print(f"claude-code-shim  http://{a.host}:{a.port}/v1   claude={claude_bin}  model={a.model}",
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
