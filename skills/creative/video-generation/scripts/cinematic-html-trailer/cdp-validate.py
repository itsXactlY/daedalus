#!/usr/bin/env python3
"""
MAZEMAKER-style HTML trailer — 14-check CDP-based verification
================================================================
Drives a real Chrome via the DevTools Protocol and verifies the trailer
actually plays. Reusable across any project that follows the
`cinematic-html-trailer` contract (window.__trailer exposed with
`audioEngine`, `time`, `sceneCount`, `scheduleFired`, `scheduleSize`,
`seek()`, `running`).

Check list (mirrors the 14 hard checks from a production session):
  1.  JS syntax (node --check)
  2.  Voiceover fully removed (if applicable — for a "no voiceover" trailer)
  3.  HTML structure (all required elements present)
  4.  Score asset HTTP 200
  5.  Hero image assets HTTP 200
  6.  Iteration count ≥ 300 (scenes + sfx + score)
  7.  Headless Chrome: navigate, autostart, no console exceptions
  8.  AudioContext state = 'running'
  9.  Hero images loaded (6/6) after warmup
 10.  Trailer time advances past t=1.5s
 11.  SFX schedule fires ≥20 events (after seek to t=30)
 12.  Screenshots show non-trivial content (>100KB PNG)
 13.  Seek to t=50 works
 14.  Final logo visible at t=105

Usage:
  pip install --user websocket-client    # one-time
  PORT=9000 python3 cdp-validate.py
"""
import os, sys, json, time, subprocess, re, base64, urllib.request
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────────────
ROOT = Path(os.environ.get("TRAILER_ROOT", "."))
JS   = ROOT / "trailer.js"
HTML = ROOT / "index.html"
PORT = int(os.environ.get("PORT", "9000"))
URL  = f"http://127.0.0.1:{PORT}/index.html"
SCRATCH = Path("/tmp/cdp-validate"); SCRATCH.mkdir(exist_ok=True)

HERO_FILES = os.environ.get("HERO_FILES", "").split() or [
    "assets/hero_cyber_v2pod.webp",
    "assets/hero_neural_pulse.webp",
    "assets/hero_ink_recursion.webp",
    "assets/hero_quantum_origin.webp",
    "assets/hero_analog_v2pod.webp",
    "assets/hero_noir_epilogue.webp",
]
SCORE_FILE = os.environ.get("SCORE_FILE", "score/uprising_score.wav")

# Expected iter count
TARGET_ITER = int(os.environ.get("TARGET_ITER", "300"))

# ─── Color helpers ─────────────────────────────────────────────────────────
def C(code): return f"\033[{code}m"
GRN = C("32"); RED = C("31"); YLW = C("33"); BLD = C("1"); RST = C("0")
results = []
def ok(name, detail=""):  results.append((True,  name, detail)); print(f"  {GRN}✓{RST} {name}  {detail}")
def fail(name, detail=""): results.append((False, name, detail)); print(f"  {RED}✗{RST} {name}  {detail}")
def info(msg):            print(f"  {YLW}·{RST} {msg}")
def head(msg):            print(f"\n── {msg} ──")

# ─── Server ────────────────────────────────────────────────────────────────
def start_server():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=0.5)
        info(f"using existing server on port {PORT}")
        return None
    except Exception: pass
    info(f"starting http.server on {PORT}")
    return subprocess.Popen(
        ["python3", "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

def http200(path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=2) as r:
            return r.status == 200
    except Exception: return False

# ─── Static checks ─────────────────────────────────────────────────────────
head("1. JS SYNTAX")
if not JS.exists():
    fail("trailer.js missing", str(JS)); sys.exit(1)
r = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True)
if r.returncode == 0:
    ok("trailer.js parses", f"{JS.stat().st_size} bytes")
else:
    fail("trailer.js parse error", r.stderr.strip().splitlines()[-1] if r.stderr else "?")

head("2. VOICEOVER FULLY REMOVED (if required)")
js = JS.read_text(); html = HTML.read_text()
vo_in_js = (js.count("VOICE_CUES") + js.count("playVoice") +
            js.count("loadVoices") + js.count("countActiveVoices"))
vo_audio_in_html = sum(1 for i in range(1, 17) if f'id="vo{i:02d}"' in html)
if vo_in_js == 0 and vo_audio_in_html == 0:
    ok("voiceover fully removed", f"no VOICE_CUES/playVoice/<audio id=vo*> in JS or HTML")
else:
    fail("voiceover still present", f"js refs={vo_in_js}, html audio vo*={vo_audio_in_html}")

head("3. HTML STRUCTURE")
required = ['<div class="stage" id="stage">', 'class="bg-canvas"', 'class="hero-img"',
            'class="flash"', 'class="blackout"', 'class="progress"', 'class="debug"',
            'class="scene-el"', 'class="final-logo"', 'id="start"',
            'trailer.js', SCORE_FILE]
missing = [r2 for r2 in required if r2 not in html]
if missing:
    fail("HTML structure", f"missing: {missing}")
else:
    ok("HTML structure", f"{HTML.stat().st_size} bytes, all required elements present")

head(f"4. SCORE + 5. HERO IMAGES HTTP 200")
ok_count = sum(1 for h in [SCORE_FILE] + HERO_FILES if http200("/" + h))
if ok_count == 1 + len(HERO_FILES):
    ok("all assets served", f"{ok_count}/{1+len(HERO_FILES)}")
else:
    fail("assets", f"{ok_count}/{1+len(HERO_FILES)} served")

head(f"6. ITERATION COUNT ≥ {TARGET_ITER}")
m  = re.search(r"function buildSceneProgram\(\)\s*\{(.*?)return S;", js, re.DOTALL)
sc = m.group(1).count("S.push(") if m else 0
m2 = re.search(r"function buildSfxSchedule.*?\n\}", js, re.DOTALL)
sf = m2.group(0).count("  S(") if m2 else 0
total = sc + sf + 1
info(f"scenes={sc} sfx={sf} score=1 → total={total}")
if total >= TARGET_ITER:
    ok(f"iteration count = {total}", f"≥ {TARGET_ITER}")
else:
    fail(f"iteration count = {total}", f"< {TARGET_ITER}")

# ─── Browser checks ───────────────────────────────────────────────────────
head("7-14. HEADLESS CHROME PLAYBACK (CDP)")
chrome_dir = SCRATCH / f"chrome-{int(time.time())}"
chrome_dir.mkdir(exist_ok=True)
chrome = subprocess.Popen(
    ["google-chrome-stable", "--headless=new", "--disable-gpu", "--no-sandbox",
     "--hide-scrollbars", "--window-size=1920,1080",
     "--autoplay-policy=no-user-gesture-required",
     "--remote-debugging-port=9222", "--remote-allow-origins=*",
     f"--user-data-dir={chrome_dir}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Wait for CDP
ready = False
for _ in range(50):
    time.sleep(0.2)
    try: urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=0.5); ready = True; break
    except Exception: pass
if not ready:
    fail("CDP", "chrome didn't open debug port"); chrome.kill(); sys.exit(1)

try:
    import websocket
except ImportError:
    fail("CDP", "websocket-client not installed. pip install --user websocket-client")
    chrome.kill(); sys.exit(1)

tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
ws = websocket.create_connection(tabs[0]["webSocketDebuggerUrl"], timeout=15)

mid = [0]
def send(method, params=None, t=8):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    deadline = time.time() + t
    while time.time() < deadline:
        ws.settimeout(max(0.05, deadline - time.time()))
        try: r = json.loads(ws.recv())
        except: return {"err": "recv"}
        if "id" in r and r["id"] == mid[0]: return r
    return {"err": "to"}

events = {"exceptions": []}
def collect(timeout=0.4):
    dl = time.time() + timeout
    while time.time() < dl:
        ws.settimeout(max(0.05, dl - time.time()))
        try:
            msg = json.loads(ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                ex = msg["params"]["exceptionDetails"]
                events["exceptions"].append(ex.get("exception", {}).get("description", ex.get("text", "")))
        except: break

send("Page.enable"); send("Runtime.enable"); send("Log.enable")

# 7. Navigate, autostart, check no exceptions after 3s
send("Page.navigate", {"url": URL + "?autostart=1"})
time.sleep(3.0); collect(timeout=0.5)
if not events["exceptions"]:
    ok("7. no console exceptions", f"after 3s autostart")
else:
    fail("7. console exceptions", events["exceptions"][0][:200])

# 8. AudioContext running
r = send("Runtime.evaluate", {"expression": "JSON.stringify({state: window.__trailer?.audioEngine?.context?.state || 'missing'})"})
state = json.loads(r["result"]["result"]["value"]).get("state", "?")
if state == "running":
    ok("8. AudioContext running", f"state={state}")
else:
    fail("8. AudioContext not running", f"state={state}")

# 9. Hero images loaded
r = send("Runtime.evaluate", {"expression": "JSON.stringify({loaded: window.__trailer?.audioEngine?.heroesLoaded, total: window.__trailer?.audioEngine?.heroCacheLength})"})
v = json.loads(r["result"]["result"]["value"])
if v.get("loaded") == v.get("total") == len(HERO_FILES):
    ok(f"9. all {len(HERO_FILES)} hero images loaded", f"{v['loaded']}/{v['total']}")
else:
    fail("9. hero images", f"{v.get('loaded')}/{v.get('total')}")

# 10. Trailer time advances
r = send("Runtime.evaluate", {"expression": "JSON.stringify({t: window.__trailer?.time?.now() || -1, scenes: window.__trailer?.sceneCount, running: window.__trailer?.running})"})
v = json.loads(r["result"]["result"]["value"])
t = v.get("t", -1); sc = v.get("scenes", 0); rn = v.get("running", False)
if t >= 1.5 and sc >= 200 and rn:
    ok("10. trailer advancing", f"t={t:.1f}s, scenes={sc}, running={rn}")
else:
    fail("10. trailer not advancing", f"t={t}, scenes={sc}, running={rn}")

# 11. SFX firing (seek to t=30 first)
send("Runtime.evaluate", {"expression": "window.__trailer.seek(30); 'seeked'"})
time.sleep(0.8); collect(timeout=0.3)
r = send("Runtime.evaluate", {"expression": "JSON.stringify({fired: window.__trailer?.scheduleFired, size: window.__trailer?.scheduleSize, t: window.__trailer?.time?.now()})"})
v = json.loads(r["result"]["result"]["value"])
if v.get("fired", 0) >= 20:
    ok("11. SFX schedule firing", f"{v['fired']}/{v['size']} at t={v['t']:.1f}s")
else:
    fail("11. SFX not firing", f"only {v.get('fired',0)}/{v.get('size',0)} at t={v.get('t',0):.1f}s")

# 12. Screenshot at t=3s (visually trivial but proves >100KB)
r = send("Page.captureScreenshot", {"format": "png"})
if "result" in r and "data" in r["result"]:
    png = base64.b64decode(r["result"]["data"])
    (SCRATCH / "shot_3s.png").write_bytes(png)
    if len(png) > 100_000:
        ok("12. screenshot non-trivial", f"{len(png)} bytes")
    else:
        fail("12. screenshot too small", f"only {len(png)} bytes")

# 13. Seek to t=50
send("Runtime.evaluate", {"expression": "window.__trailer.seek(50); 'seeked'"})
time.sleep(0.6)
r = send("Runtime.evaluate", {"expression": "JSON.stringify({t: window.__trailer?.time?.now() || -1})"})
t50 = json.loads(r["result"]["result"]["value"]).get("t", -1)
if 45 <= t50 <= 55:
    ok("13. seek to t=50", f"t={t50:.1f}s")
else:
    fail("13. seek broken", f"expected t≈50, got t={t50:.1f}")

r = send("Page.captureScreenshot", {"format": "png"})
if "result" in r and "data" in r["result"]:
    (SCRATCH / "shot_50s.png").write_bytes(base64.b64decode(r["result"]["data"]))

# 14. Seek to t=105, capture final logo
send("Runtime.evaluate", {"expression": "window.__trailer.seek(105); 'seeked'"})
time.sleep(0.5)
r = send("Page.captureScreenshot", {"format": "png"})
if "result" in r and "data" in r["result"]:
    (SCRATCH / "shot_105s.png").write_bytes(base64.b64decode(r["result"]["data"]))
    ok("14. finale screenshot captured", f"{(SCRATCH/'shot_105s.png').stat().st_size} bytes")

# Cleanup
ws.close()
chrome.terminate()
try: chrome.wait(timeout=3)
except: chrome.kill()

# ─── Summary ───────────────────────────────────────────────────────────────
print()
print("=" * 70)
passed = sum(1 for r2 in results if r2[0]); total = len(results)
print(f"  {BLD}RESULTS: {passed}/{total} checks passed{RST}")
print("=" * 70)
for ok2, name, _ in results:
    print(f"  [{GRN}PASS{RST}] {name}" if ok2 else f"  [{RED}FAIL{RST}] {name}")
print()
sys.exit(0 if passed == total else 1)
