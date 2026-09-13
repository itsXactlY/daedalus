"""Offline e2e test for the mazemaker dispatcher fixes.

Stubs module-level _tool (no live pod) so we can drive handle_tool_call and
assert:
  A. dispatcher unwrap: {"tool": ..., "memory_ids": [...]} passes memory_ids
     through to _tool (the dropped-args bug).
  B. sanitizer: an int top-level 'id' in the pod result is stringified in the
     returned JSON (the Cohere 'id must be a string' 400 trigger).
  C. sub-tool auto-repair contract: calling the dispatcher with a bare sub-tool
     name at top level still works because we no longer require 'args'.
"""
import json
import sys

ROOT = "/home/alca/.daedalus/daedalus-agent"
sys.path.insert(0, ROOT)

import plugins.memory.mazemaker as mm

CAPTURED = {}

def fake_tool(name, arguments, timeout=8.0):
    CAPTURED["name"] = name
    CAPTURED["arguments"] = dict(arguments)
    # Simulate the pod's mazemaker_get not-found result with an INTEGER id —
    # the exact shape that poisoned the Cohere channel.
    return {
        "id": 1,
        "found": False,
        "max_id_in_store": 1220813,
        "nearest_above": [{"id": 1256, "label": "peer:alca"}],
    }

mm._tool = fake_tool  # monkeypatch module-level _tool

provider = mm.MazemakerMemoryProvider()

def run(args, tag):
    out = provider.handle_tool_call("mazemaker", args, **{})
    parsed = json.loads(out)
    return CAPTURED, parsed

failures = []

# A. correct dispatcher call: tool + memory_ids at top level.
cap, parsed = run({"tool": "mazemaker_get", "memory_ids": [1219477]}, "A")
if cap["name"] != "mazemaker_get":
    failures.append(f"A: dispatcher did not unwrap tool -> got {cap['name']!r}")
if cap["arguments"].get("memory_ids") != [1219477]:
    failures.append(f"A: memory_ids dropped -> got {cap['arguments']}")
if not isinstance(parsed.get("id"), str) or parsed.get("id") != "1":
    failures.append(f"A: id not stringified -> {parsed.get('id')!r}")
if not all(isinstance(n.get("id"), str) for n in parsed.get("nearest_above", [])):
    failures.append(f"A: nested id not stringified -> {parsed.get('nearest_above')}")
print("A dispatcher unwrap + sanitize:", "OK" if not failures else "FAIL")

# B. the poisoned shape the model produced: tool present, memory_ids present,
#    but the sanitizer must still stringify (regression guard).
cap, parsed = run({"tool": "mazemaker_get", "memory_ids": [1219477], "max_chars": 0}, "B")
if parsed.get("id") != "1":
    failures.append(f"B: id wrong -> {parsed.get('id')!r}")
print("B regression shape:", "OK" if not failures else "FAIL")

# C. help path still returns help text, not the 'requires a tool name' error.
help_out = provider.handle_tool_call("mazemaker", {"tool": "mazemaker_get"})
if 'requires a \'tool\' name' in help_out:
    failures.append("C: help path still errors")
print("C help path:", "OK" if not failures else "FAIL")

print()
if failures:
    print("FAILURES:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("ALL PASSED")
