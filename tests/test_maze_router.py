from __future__ import annotations
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from agent.maze_router import (Assembler, Budget, DISTILLED_BOOST, HeuristicPlanner, Hit,
                               LlmPlanner, TRANSCRIPT_PENALTY, _kind_weight,
                               MAX_BATCH_GET, Material, MazeRouter, PodClient, PodError)

FAIL = []
def check(name, cond, detail=""):
    if cond: print(f"    PASS  {name}")
    else: FAIL.append(name); print(f"    FAIL  {name}  {detail}")


class FakePod(PodClient):
    def __init__(self, hits=None, raises=None, full=None):
        self.recall_calls = 0; self.multi_calls = 0; self.get_calls = 0
        self.last_ids = []
        self._hits = hits if hits is not None else [
            Hit(i, f"label{i}", f"snippet {i} " + "x"*50, 1.0 - i*0.01) for i in range(1, 13)]
        self._raises = raises
        self._full = full if full is not None else {i: f"FULLTEXT {i} " + "y"*400 for i in range(1, 13)}

    def recall(self, query, limit, timeout_s):
        self.recall_calls += 1
        if self._raises: raise self._raises
        return self._hits[:limit]

    def recall_multi(self, queries, limit, timeout_s):
        self.multi_calls += 1
        if self._raises: raise self._raises
        return self._hits[:limit*len(queries)]

    def get_many(self, memory_ids, timeout_s):
        self.get_calls += 1
        self.last_ids = list(memory_ids)
        if self._raises: raise self._raises
        return {i: self._full[i] for i in memory_ids if i in self._full}


print("  == the chain: recall -> ids -> ONE batch get ==")
pod = FakePod(); r = MazeRouter(pod, HeuristicPlanner(), Budget(hits_per_angle=8, expand_top_n=6))
m = r.fetch("what did we decide about the dream worker")
check("returns Material", isinstance(m, Material))
check("material not empty", not m.empty)
check(f"exactly ONE get call (saw {pod.get_calls})", pod.get_calls == 1)
check(f"get was batched (saw {len(pod.last_ids)} ids)", len(pod.last_ids) == 6)
check("never expands more than recalled", len(pod.last_ids) <= len(m.hits))
check("expanded ids reported", len(m.expanded_ids) == 6)
check("full text preferred over snippet", "FULLTEXT" in m.text)

print("  == multi-topic uses recall_multi, still one get ==")
pod = FakePod(); r = MazeRouter(pod, HeuristicPlanner(), Budget())
m = r.fetch("compare podman and docker, and tell me the quadlet units, and the rootless notes")
check(f"planner found multiple angles ({len(m.angles)})", len(m.angles) > 1)
check("used recall_multi", pod.multi_calls == 1 and pod.recall_calls == 0)
check(f"still ONE get (saw {pod.get_calls})", pod.get_calls == 1)

print("  == dedupe across angles ==")
dup = [Hit(7, "l", "s", 0.4), Hit(7, "l", "s", 0.9), Hit(8, "l", "s", 0.5)]
pod = FakePod(hits=dup); r = MazeRouter(pod, HeuristicPlanner(), Budget())
m = r.fetch("one topic only here please")
ids = [h.memory_id for h in m.hits]
check("no duplicate ids", len(ids) == len(set(ids)))
check("kept the higher score", next(h.score for h in m.hits if h.memory_id == 7) == 0.9)
check("sorted by score desc", ids == sorted(ids, key=lambda i: -next(h.score for h in m.hits if h.memory_id==i)))

print("  == distilled facts outrank raw transcripts ==")
check("fact: boosted", _kind_weight("fact:btquant-overview") == DISTILLED_BOOST)
check("afe boosted", _kind_weight("session:x::afe-block0::afe::C3") == DISTILLED_BOOST)
check("auto:turn penalised", _kind_weight("auto:turn:abc") == TRANSCRIPT_PENALTY)
check("unknown neutral", _kind_weight("skillsrc:local:x") == 1.0)
_mix = [Hit(1,"auto:turn:echo","q",0.807), Hit(2,"fact:the-answer","a",0.609)]
_r = MazeRouter(FakePod(hits=_mix), HeuristicPlanner(), Budget())
_m = _r.fetch("a question about some topic here")
check("fact ranks above higher-sim transcript", _m.hits[0].label.startswith("fact:"),
      f"got {_m.hits[0].label}")

print("  == overfetch widens the pool before ranking ==")
class CountingPod(FakePod):
    def __init__(self): super().__init__(); self.asked = None
    def recall(self, query, limit, timeout_s):
        self.asked = limit; return super().recall(query, limit, timeout_s)
_cp = CountingPod()
MazeRouter(_cp, HeuristicPlanner(), Budget(hits_per_angle=5, overfetch=4)).fetch("a single topic question here")
check(f"recall asked for hits*overfetch (saw {_cp.asked})", _cp.asked == 20)
try: Budget(overfetch=0); check("rejects overfetch=0", False)
except ValueError: check("rejects overfetch=0", True)

print("  == material is bounded ==")
big = {i: "Z"*100_000 for i in range(1, 13)}
pod = FakePod(full=big); b = Budget(material_chars=2000)
m = MazeRouter(pod, HeuristicPlanner(), b).fetch("a single topic question about something")
check(f"material <= budget ({len(m.text)} <= 2000)", len(m.text) <= 2000)

print("  == fail-open ==")
pod = FakePod(raises=PodError("pod down"))
m = MazeRouter(pod, HeuristicPlanner(), Budget()).fetch("anything at all goes here")
check("returns empty Material, no raise", isinstance(m, Material) and m.empty)
r2 = MazeRouter(FakePod(raises=RuntimeError("boom")), HeuristicPlanner(), Budget())
m2 = r2.fetch("another question entirely")
check("failed_open counted", r2.telemetry.snapshot()["failed_open"] == 1)

print("  == planner ==")
h = HeuristicPlanner(); b = Budget(max_angles=4)
check("trivial input -> no angles", h.angles("", b) == [] and h.angles("ok", b) == [])
check("noise prefix stripped", not h.angles("please tell me about the dream worker config", b)[0].lower().startswith("please"))
check("angles capped", len(h.angles("aaaaaaaaaaaa and bbbbbbbbbbbb and cccccccccccc and dddddddddddd and eeeeeeeeeeee", b)) <= 4)
lp = LlmPlanner("http://127.0.0.1:1/v1", "nope", timeout_s=1.0)
check("LlmPlanner falls back when endpoint dead", len(lp.angles("compare a thing and another thing", b)) >= 1)

print("  == guard rails ==")
for bad, label in ((lambda: Budget(max_angles=0), "max_angles=0"),
                   (lambda: Budget(hits_per_angle=0), "hits_per_angle=0"),
                   (lambda: Budget(expand_top_n=99), "expand_top_n>25"),
                   (lambda: Budget(material_chars=10), "tiny material")):
    try: bad(); check(f"rejects {label}", False, "no error")
    except ValueError: check(f"rejects {label}", True)
check("MAX_BATCH_GET is 25", MAX_BATCH_GET == 25)
pod = FakePod(); MazeRouter(pod, HeuristicPlanner(), Budget(expand_top_n=25)).fetch("one topic here for the cap test")
check(f"batch never exceeds 25 (saw {len(pod.last_ids)})", len(pod.last_ids) <= 25)

print()
if FAIL: print(f"  {len(FAIL)} FAILURES: {FAIL}"); sys.exit(1)
print("  ALL PASS")
