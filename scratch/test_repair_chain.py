"""Verify the full auto-repair chain in run_agent.py (unit, no API)."""
import sys, os, json, types
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_agent

# Minimal stand-in: bind only the methods under test.
class Dummy:
    pass
d = Dummy()
d.tools = [
    {"function": {"name": "mazemaker",
                  "parameters": {"type": "object",
                                 "properties": {"tool": {"type": "string"},
                                                "args": {"type": "object"}},
                                 "required": ["tool"]}}},
    {"function": {"name": "terminal",
                  "parameters": {"type": "object",
                                 "properties": {"command": {"type": "string"}}}}},
]
d.valid_tool_names = {"mazemaker", "terminal"}
d._repair_tool_call = run_agent.AIAgent._repair_tool_call.__get__(d)
d._tool_schema = run_agent.AIAgent._tool_schema.__get__(d)
d._repair_dispatcher_args = run_agent.AIAgent._repair_dispatcher_args.__get__(d)

# --- Simulate the exact broken-session call: model calls mazemaker_get natively ---
tc = types.SimpleNamespace(
    function=types.SimpleNamespace(name="mazemaker_get",
                                    arguments=json.dumps({"memory_ids": [1219477]})))
orig = tc.function.name
repaired = d._repair_tool_call(orig)
print("repaired name:", repaired)
assert repaired == "mazemaker"
tc.function.name = repaired  # harness reassigns before calling repair (run_agent.py:10100-10101)
d._repair_dispatcher_args(tc, orig)  # harness passes the ORIGINAL name as orig_name
print("repkgaged args:", tc.function.arguments)
expected = json.dumps({"tool": "mazemaker_get", "args": {"memory_ids": [1219477]}})
assert tc.function.arguments == expected, tc.function.arguments
print("chain step 1: PASS")

# --- No-op: already dispatcher-shaped ---
tc2 = types.SimpleNamespace(
    function=types.SimpleNamespace(name="mazemaker",
                                    arguments=json.dumps({"tool": "mazemaker_get",
                                                        "args": {"memory_ids": [1]}})))
d._repair_dispatcher_args(tc2, "mazemaker")
assert json.loads(tc2.function.arguments) == {"tool": "mazemaker_get", "args": {"memory_ids": [1]}}
print("no-op case: PASS")

# --- No-op: tool without required 'tool' field (terminal) ---
tc3 = types.SimpleNamespace(
    function=types.SimpleNamespace(name="terminal",
                                    arguments=json.dumps({"command": "ls"})))
d._repair_dispatcher_args(tc3, "terminal")
assert tc3.function.arguments == json.dumps({"command": "ls"})
print("non-dispatcher no-op: PASS")

# --- Malformed args don't crash ---
tc4 = types.SimpleNamespace(
    function=types.SimpleNamespace(name="mazemaker", arguments="not-json"))
d._repair_dispatcher_args(tc4, "mazemaker")
print("malformed args ok:", tc4.function.arguments)

print("=== ALL PASS ===")
