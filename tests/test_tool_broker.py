from __future__ import annotations
import sys
sys.path.insert(0, "/home/alca/.daedalus")
from agent.tool_broker import (CallableExecutor, HeuristicMapper, ToolAdvisor,
                               ToolBroker, ToolRequest, ToolResult)

FAIL=[]
def check(n,c,d=""):
    if c: print(f"    PASS  {n}")
    else: FAIL.append(n); print(f"    FAIL  {n}  {d}")

AV = {"terminal","read_file","write_file","search_files","mazemaker_recall"}

print("  == NEED parsing ==")
check("plain", ToolRequest.parse("NEED: read /etc/hosts").text == "read /etc/hosts")
check("after prose", ToolRequest.parse("Sure.\nNEED: run: git log -1").text == "run: git log -1")
check("case insensitive", ToolRequest.parse("need: do a thing") is not None)
check("absent -> None", ToolRequest.parse("just an answer") is None)
check("empty -> None", ToolRequest.parse("NEED:   ") is None)
check("no reply -> None", ToolRequest.parse("") is None)

print("  == mapping ==")
m=HeuristicMapper()
check("read+path -> read_file", m.plan("read /home/x/config.yaml", AV).tool == "read_file")
check("run: -> terminal", m.plan("run: git log -1", AV).tool == "terminal")
check("search -> search_files", m.plan("search for maze_router", AV).tool == "search_files")
check("memory cue -> recall", m.plan("what did we decide earlier", AV).tool == "mazemaker_recall")
check("network PROSE is refused (not shell-executed)", m.plan("curl the github api", AV) is None)
check("explicit network command works", m.plan("run: curl -s https://api.github.com", AV).tool == "terminal")
check("unmappable -> None", m.plan("ponder the meaning of things", set()) is None)
check("respects availability", m.plan("run: ls", {"read_file"}) is None)
_w = m.plan("write /tmp/a.html: <html>x</html>", AV)
check("write -> write_file", _w.tool == "write_file")
check("write path parsed", _w.args["path"] == "/tmp/a.html")
check("write content parsed", _w.args["content"] == "<html>x</html>")
check("read uses 'path' arg", m.plan("read /etc/hosts", AV).args.get("path") == "/etc/hosts")
_wn = m.plan("write /tmp/b.md\n# Title", AV)
check("newline form parsed", _wn.tool == "write_file" and _wn.args["content"] == "# Title")

print("  == NEVER shell-execute raw model text ==")
_m = HeuristicMapper()
for _txt, _lbl in (
    ("<html><head><style>body{color:red}</style></head></html>", "raw HTML"),
    ("<!DOCTYPE html>\n<html lang=en>\n<body>hi</body>\n</html>", "multiline HTML"),
    ("curl https://api.github.com/repos/x/y", "bare url prose"),
    ("check /home/alca/projects for the readme", "prose with a path"),
    ("rm -rf / please", "dangerous prose"),
    ("the file /etc/passwd is interesting", "path mention"),
):
    _p = _m.plan(_txt, AV)
    check(f"{_lbl} is NOT shell-executed", _p is None or _p.tool != "terminal",
          f"got {_p.tool if _p else None}")
_ok = _m.plan("run: ls /tmp", AV)
check("explicit 'run:' still reaches terminal", _ok and _ok.tool == "terminal")
check("explicit command is stripped", _ok.args["command"] == "ls /tmp")
_ml = _m.plan("run: ls\nrm -rf /", AV)
check("multiline command never reaches shell whole",
      _ml is None or "rm -rf" not in _ml.args.get("command", ""))
_long = _m.plan("run: " + "x"*500, AV)
check("over-long command refused", _long is None)

print("  == broker execution ==")
calls=[]
ex=CallableExecutor(lambda n,a: (calls.append((n,a)), "OUTPUT")[1], AV)
b=ToolBroker(ex)
r=b.serve("ok.\nNEED: run: ls /tmp")
check("served", r.ok and r.tool=="terminal")
check("executor called once", len(calls)==1)
check("material formatted", "RESULT of" in r.as_material() and "OUTPUT" in r.as_material())
check("stats served=1", b.stats["served"]==1)
check("no NEED -> None", b.serve("no request here") is None)

print("  == failure paths ==")
b2=ToolBroker(CallableExecutor(lambda n,a: (_ for _ in ()).throw(RuntimeError("boom")), AV))
r2=b2.serve("NEED: run: explode")
check("failure captured, not raised", r2 is not None and not r2.ok)
check("failed counted", b2.stats["failed"]==1)
b3=ToolBroker(CallableExecutor(lambda n,a:"x", set()))
r3=b3.serve("NEED: something impossible")
check("refused when nothing matches", r3 is not None and not r3.ok)
check("refused counted", b3.stats["refused"]==1)
check("no executor -> None", ToolBroker(None).serve("NEED: x") is None)

print("  == native tool-call formats ==")
_x = ToolRequest.parse("ok\n<tool_call><function=terminal><parameter=command>ls /tmp</parameter></function></tool_call>")
check("xml parsed", _x is not None and _x.tool == "terminal")
check("xml args parsed", _x.args.get("command") == "ls /tmp")
check("xml marked explicit", _x.explicit)
_j = ToolRequest.parse('<tool_call>{"name":"read_file","arguments":{"path":"/etc/hosts"}}</tool_call>')
check("json parsed", _j is not None and _j.tool == "read_file" and _j.args.get("path") == "/etc/hosts")
check("NEED still wins", ToolRequest.parse("NEED: run: ls").tool == "")
check("prose still None", ToolRequest.parse("no call here") is None)
_bex = ToolBroker(CallableExecutor(lambda n,a: "RAN " + n, AV))
_ok = _bex.serve("<tool_call><function=terminal><parameter=command>ls</parameter></function></tool_call>")
check("explicit known tool executes", _ok.ok and _ok.tool == "terminal")
_no = _bex.serve("<tool_call><function=task_tool><parameter=path>/tmp</parameter></function></tool_call>")
check("explicit UNKNOWN tool refuses", not _no.ok and _no.tool == "")
check("refusal names the tool", "task_tool" in (_no.output or ""))
check("unknown tool is NOT shell-executed", "RAN" not in (_no.output or ""))

print("  == advisor is task specific ==")
a=ToolAdvisor()
check("github -> network advice", "network" in a.advise("last commit on the github repo"))
check("file -> read advice", "read" in a.advise("show me the config file"))
check("search -> search advice", "searched" in a.advise("find where maze_router is used"))
check("vague -> empty", a.advise("hello there") == "")

print("  == output is capped ==")
big=ToolBroker(CallableExecutor(lambda n,a:"Z"*50_000, AV)).serve("NEED: run: yes")
check("material capped", len(big.as_material(1000)) <= 1100)

print()
if FAIL: print(f"  {len(FAIL)} FAILURES: {FAIL}"); sys.exit(1)
print("  ALL PASS")
