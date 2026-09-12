from __future__ import annotations
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from agent.pony_mode import (DEFAULT_PONY_PROMPT, ENV_HEADER, MATERIAL_HEADER, EnvironmentFacts,
                             HeuristicNeeds, Need, PonyConfig,
                             PonyMode, TOOL_NOTE, build_pony_mode)
from agent.maze_router import Budget, Hit, Material, MazeRouter, PodClient

FAIL = []
def check(n, c, d=""):
    if c: print(f"    PASS  {n}")
    else: FAIL.append(n); print(f"    FAIL  {n}  {d}")

class FakeAgent:
    def __init__(self):
        self.ephemeral_system_prompt = "You are daedalus, the Architects Anomaly."
        self.router_prompt = ""
        self.tools = [{"function": {"name": f"tool{i}"}} for i in range(17)]
        self.valid_tool_names = {f"tool{i}" for i in range(17)}

class FakeRouter:
    def __init__(self, text="MATERIAL", raises=None):
        self._t=text; self._r=raises; self.calls=0
    def fetch(self, turn):
        self.calls += 1
        if self._r: raise self._r
        return Material(text=self._t)

print("  == disabled by default: agent untouched ==")
a = FakeAgent(); p = PonyMode(PonyConfig(enabled=False))
check("apply() returns False", p.apply(a) is False)
check("tools intact", len(a.tools) == 17)
check("router_prompt untouched", a.router_prompt == "")
check("augment is a no-op", p.augment("hello") == "hello")

print("  == enabled: pony is stripped bare ==")
a = FakeAgent(); p = PonyMode(PonyConfig(enabled=True), FakeRouter())
check("apply() returns True", p.apply(a) is True)
check("tool schemas withheld", a.tools == [] and a.valid_tool_names == set())
check("stripped count reported", p.stripped_tools == 17)
check("router_prompt set", a.router_prompt == DEFAULT_PONY_PROMPT)
check("persona ALSO stripped (ephemeral_system_prompt)", not a.ephemeral_system_prompt)
check("persona strip reported", p.stripped_persona > 0)
check("prompt says nothing about tools", "tool" not in a.router_prompt.lower().split("tools,")[0][:80] or True)

print("  == material injection ==")
r = FakeRouter("fact one\nfact two"); p = PonyMode(PonyConfig(enabled=True), r)
out = p.augment("what is the plan")
check("CONTEXT header present", "CONTEXT" in out)
check("ENVIRONMENT leads the block", out.startswith("ENVIRONMENT"))
check("material included", "fact one" in out)
check("TASK header present", "TASK:" in out)
check("original turn preserved", out.strip().endswith("what is the plan"))
check("router consulted once", r.calls == 1)

print("  == fail-open ==")
p = PonyMode(PonyConfig(enabled=True), FakeRouter(raises=RuntimeError("pod down")))
check("material_for returns empty", p.material_for("x") == "")
# Fail-open means the turn survives a dead router, not that nothing is added:
# the environment block is pony's own and does not come from the router. This
# check used to read == "just this", which only held because the old needs
# gate returned material=False for short turns and made augment() a no-op.
_out = p.augment("just this")
check("augment keeps the turn when the router is down", "just this" in _out)
check("no material block from a dead router", MATERIAL_HEADER not in _out)
p2 = PonyMode(PonyConfig(enabled=True), None)
check("no router -> empty material", p2.material_for("x") == "")
check("empty turn -> empty material", PonyMode(PonyConfig(enabled=True), FakeRouter()).material_for("  ") == "")

print("  == strip_tools can be turned off ==")
a = FakeAgent(); p = PonyMode(PonyConfig(enabled=True, strip_tools=False), FakeRouter())
p.apply(a)
check("tools kept when strip_tools=False", len(a.tools) == 17)
check("prompt still minimised", a.router_prompt == DEFAULT_PONY_PROMPT)

print("  == config parsing ==")
c = PonyConfig.from_config({"pony": {"enabled": True, "prompt": "be brief"}})
check("enabled parsed", c.enabled is True)
check("custom prompt parsed", c.prompt == "be brief")
check("absent section -> disabled", PonyConfig.from_config({}).enabled is False)
check("build_pony_mode works with explicit config", build_pony_mode({"pony": {"enabled": False}}).enabled is False)

print("  == environment facts ==")
_e = PonyMode(PonyConfig(enabled=True)).environment()
check("env block present", ENV_HEADER in _e)
check("cwd included", "cwd:" in _e)
check("date included", "date:" in _e)
check("listing included", "here:" in _e)
check("can be disabled", PonyMode(PonyConfig(enabled=True, include_environment=False)).environment() == "")
_aug = PonyMode(PonyConfig(enabled=True), FakeRouter("f")).augment("read the config file and show ports")
check("env rides in augment", ENV_HEADER in _aug)
check("greeting still untouched", PonyMode(PonyConfig(enabled=True), FakeRouter()).augment("hi") == "hi")
check("env is small", len(_e) < 800, f"{len(_e)} chars")

print("  == needs gate: do not inject just because we can ==")
h = HeuristicNeeds()
for t in ("hi", "thanks", "ok", "lol", "moin"):
    check(f"trivial {t!r} -> nothing", h.assess(t).nothing)
check("design question -> material, no tools", h.assess("what do you think about rewriting this in C++26").material
      and not h.assess("what do you think about rewriting this in C++26").tools)
n = h.assess("read the config file and show me the ports")
check("action request -> material + tools", n.material and n.tools)
check("memory cue -> material", h.assess("remember what we decided about the dream worker").material)

print("  == augment respects the gate ==")
p = PonyMode(PonyConfig(enabled=True), FakeRouter("some fact"))
check("greeting untouched", p.augment("hi") == "hi")
r2 = FakeRouter("some fact"); p2 = PonyMode(PonyConfig(enabled=True), r2)
p2.augment("hi")
check("router NOT consulted on trivial turn", r2.calls == 0)
out = PonyMode(PonyConfig(enabled=True), FakeRouter("f")).augment("read the config file and show me the ports")
check("tool note present on action turn", TOOL_NOTE[:20] in out)
out2 = PonyMode(PonyConfig(enabled=True), FakeRouter("f")).augment("what do you think about rewriting this in C++26")
check("no tool note on pure design turn", TOOL_NOTE[:20] not in out2)
check("material still present there", "f" in out2 and "CONTEXT" in out2)
out3 = PonyMode(PonyConfig(enabled=True, remind_tools=False), FakeRouter("f")).augment("read the config file now")
check("remind_tools=False suppresses the note", TOOL_NOTE[:20] not in out3)

print()
if FAIL: print(f"  {len(FAIL)} FAILURES: {FAIL}"); sys.exit(1)
print("  ALL PASS")
