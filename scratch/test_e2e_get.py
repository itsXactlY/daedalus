import sys, importlib.util, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import plugins.memory.mazemaker as m

print("WONDERLAND_URL =", m.WONDERLAND_URL)

prov = m.MazemakerMemoryProvider()

# --- Case A: the EXACT failing call from the log (no 'tool' key, only memory_ids) ---
rA = prov.handle_tool_call("mazemaker_get", {"memory_ids": [1219477]})
print("\n=== CASE A: handle_tool_call('mazemaker_get', {'memory_ids':[1219477]}) ===")
print("type:", type(rA).__name__)
try:
    dA = json.loads(rA)
except Exception as e:
    print("not JSON:", rA[:300]); dA = None
okA = False
if isinstance(dA, dict):
    # pod batch shape: {"count": N, "results": [{"id":..., "found":..., "memory":{...}}]}
    results = dA.get("results", [])
    if results:
        r0 = results[0]
        rid = r0.get("id")
        found = r0.get("found")
        mem = r0.get("memory", {})
        print("results[0].id:", rid, "(type %s)" % type(rid).__name__)
        print("results[0].found:", found)
        print("memory label:", mem.get("label"))
        content = mem.get("content", "")
        print("content chars:", len(content))
        print("content_preview:", str(content)[:120])
        # the exact failure was: pod returned id 1 / found false. Now it must return 1219477 / true.
        okA = (str(rid) == "1219477" and found is True and len(content) > 0)
    # assert EVERY id field in the whole payload is a string (Cohere-safe)
    def check(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "id":
                    assert isinstance(v, str), f"NON-STRING id: {v!r}"
                check(v)
        elif isinstance(o, list):
            for x in o:
                check(x)
    check(dA)
    print("all id fields are STRINGS -> Cohere-safe")
print("CASE A:", "PASS" if okA else "FAIL")

# --- Case B: explicit dispatcher form (as the model eventually called it) ---
rB = prov.handle_tool_call("mazemaker", {"tool": "mazemaker_get", "memory_ids": [1219477]})
print("\n=== CASE B: handle_tool_call('mazemaker', {'tool':'mazemaker_get','memory_ids':[1219477]}) ===")
try:
    dB = json.loads(rB)
    rb = dB.get("results", [{}])[0]
    print("results[0].id:", rb.get("id"), "found:", rb.get("found"))
except Exception:
    print("raw:", str(rB)[:200])

print("\n=== CASE A raw ===")
print(repr(rA)[:600])
print("\n=== CASE B raw ===")
print(repr(rB)[:600])
print("\n=== DONE ===")
