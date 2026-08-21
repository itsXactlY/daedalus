# Headless Capture & Testing

Two distinct needs that both look like "headless rendering":

1. **Final video output** — render the trailer to an `.mp4` (Path A or B below).
2. **Verification of behavior** — prove the trailer actually plays, no console
   exceptions, audio context is running, scenes are activating, SFX schedule
   is firing. This is what `validate.py` does. See "CDP-based testing" below.

`chrome --headless --screenshot --virtual-time-budget=N` is the standard
documentation recipe but it **does NOT advance the requestAnimationFrame loop**.
Five+ attempts in a real session all captured the start screen, not the
in-trailer state, regardless of budget value. Don't waste time on it.

The reliable way to verify an animated HTML trailer headlessly is **Chrome
DevTools Protocol (CDP) over WebSocket**. A reusable script for this lives
in `scripts/cdp-validate.py`.

---

## CDP-based testing (verification of behavior)

Launch chrome with remote debugging, then drive it from Python via CDP. The
script captures real state, real exceptions, real screenshots.

```python
import json, time, base64, urllib.request
import websocket   # pip install websocket-client

# Start chrome
chrome = subprocess.Popen([
    "google-chrome-stable", "--headless=new", "--disable-gpu", "--no-sandbox",
    "--hide-scrollbars", "--window-size=1920,1080",
    "--autoplay-policy=no-user-gesture-required",
    "--remote-debugging-port=9222", "--remote-allow-origins=*",   # ← critical
    f"--user-data-dir=/tmp/chrome-cdp-{int(time.time())}",
    "about:blank",
])

# Wait for CDP, connect, get page websocket
for _ in range(40):
    time.sleep(0.2)
    try: urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=0.5); break
    except: pass

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
    return {"err": "timeout"}

# Enable domains, navigate, capture state
send("Page.enable"); send("Runtime.enable"); send("Log.enable")
send("Page.navigate", {"url": URL + "?autostart=1"})
time.sleep(3.0)

# Check AudioContext state via the trailer's exposed API
r = send("Runtime.evaluate", {
    "expression": "JSON.stringify({state: window.__trailer?.audioEngine?.context?.state || 'missing'})"
})
ctx_state = json.loads(r["result"]["result"]["value"]).get("state")

# Check trailer time is advancing
r = send("Runtime.evaluate", {
    "expression": "JSON.stringify({t: window.__trailer?.time?.now() || -1, scenes: window.__trailer?.sceneCount, running: window.__trailer?.running})"
})
state = json.loads(r["result"]["result"]["value"])
if state["t"] >= 1.5 and state["scenes"] >= 200 and state["running"]:
    print("trailer advancing OK")

# Seek to a known time and capture screenshot
send("Runtime.evaluate", {"expression": "window.__trailer.seek(50); 'seeked'"})
time.sleep(0.6)
r = send("Page.captureScreenshot", {"format": "png"})
with open("/tmp/shot_50s.png", "wb") as f:
    f.write(base64.b64decode(r["result"]["data"]))

# Cleanup
ws.close()
chrome.terminate()
chrome.wait(timeout=3)
```

### Critical flags

- **`--remote-allow-origins=*`** — without this, Chrome 100+ rejects the CDP
  WebSocket from `127.0.0.1` with `Handshake status 403 Forbidden`.
- **`--autoplay-policy=no-user-gesture-required`** — needed for
  `AudioContext` and `<audio>.play()` to succeed without a real click.
- **`--user-data-dir=<unique>`** — Chrome refuses to share its default profile
  with headless. Generate a fresh tmp dir per run.
- **`--headless=new`** — the new headless mode renders correctly with Web Audio
  and Canvas. The legacy `--headless` flag is more limited.

### Catching exceptions

The trailer may have a runtime error (TDZ, missing element, etc.) that the
page silently swallows. Listen for `Runtime.exceptionThrown` events:

```python
exceptions = []
def collect(timeout=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ws.settimeout(max(0.05, deadline - time.time()))
        try:
            msg = json.loads(ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                ex = msg["params"]["exceptionDetails"]
                exceptions.append(ex.get("exception", {}).get("description", ex.get("text", "")))
        except: break
```

If `exceptions` is non-empty after the test, the trailer is broken even if
the start screen renders. The user is staring at a black page.

### Why not `--screenshot --virtual-time-budget`?

It's tempting to just take a screenshot at virtual time N. But:

- The page's `requestAnimationFrame` loop is gated on real frame scheduling,
  not virtual time. At virtual time N, the rAF may have run 0 times.
- `audio.currentTime` is bound to real audio decoding, not virtual time.
- Score fade-in driven by `setInterval` will not have run at all.

CDP-based testing with real time + a few seconds of real wait is the only
reliable way to capture mid-trailer state. Use the `?time=X` URL param if
you specifically need a particular moment — it seeks the internal clock
after start.

---

## Path A: Xvfb + Chrome + ffmpeg x11grab (final MP4 render)

This is the canonical render path. See `mazemaker-viral-trailer` skill →
`references/headless-video-render.md` for the exact script.

```bash
# Prerequisites
sudo pacman -S xorg-server-xvfb    # Arch
google-chrome-stable                # or firefox

# Serve the HTML via HTTP (not file:// — Chrome blocks file:// image loads)
python3 -m http.server 31999 &

# Render
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -ac &
sleep 2
google-chrome-stable --no-sandbox --new-window --window-size=1920,1080 \
  --start-fullscreen --user-data-dir=/tmp/chrome-trailer \
  "http://127.0.0.1:31999/trailer.html"
sleep 4
xdotool mousemove 960 540 click 1
ffmpeg -y -f x11grab -framerate 30 -s 1920x1080 -i :99.0 \
  -i soundtrack.flac \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p \
  -c:a aac -b:a 320k -ar 48000 -ac 2 \
  -t 46 -movflags +faststart \
  trailer-final.mp4
```

**CRITICAL RULES for capture:**
- **Serve via HTTP, NOT file://** — `google-chrome-stable` blocks `file://`
  image loads from local HTML when launched with `--no-sandbox`.
  Use `python3 -m http.server <port>` and access via `http://127.0.0.1:<port>/`.
- **Fresh temp profile** — `--user-data-dir=/tmp/chrome-trailer` (never use
  the user's real Chrome profile). Clean up after: `rm -rf /tmp/chrome-trailer`.
- **Click timing** — click AFTER ffmpeg starts recording, not before, so the
  timeline starts from the capture's beginning.
- **Duration** — `-t` must match the HTML's `END_AT` constant + 0.5s buffer.
- **Chrome is preferred** — Firefox/Wayland renders via GPU compositing that
  doesn't write to the X11 framebuffer (black capture output). See
  `mazemaker-viral-trailer` skill's render reference for details.

## Path B: ffmpeg Crop Ken Burns (fallback, no browser)

If the user forbids Chrome/browser use entirely, or no browser is available,
render still image sequences to video using ffmpeg's `crop` filter.

This produces a video WITHOUT CSS animations (shake, glitch, bloom). Only
camera drift and typography overlays.

See `comfyui` skill → `references/crop-ken-burns.md` for the full technique.

Workflow:
1. Generate still images per act/timeline (e.g. via ComfyUI/Flux)
2. Pre-scale to 110% (PIL LANCZOS)
3. ffmpeg crop each still with animated position → short clips
4. Concat all clips
5. Overlay typography via ASS subtitle file
6. Mux with soundtrack
7. Optional second pass: flash frames, bloom, chromatic aberration overlays

**Total render time for 24 shots at 45.5s / 30fps:** ~30 seconds.
