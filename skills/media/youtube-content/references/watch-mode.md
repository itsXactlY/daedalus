# Full Watch Mode — visual channel reconstruction

Proven end-to-end 2026-08-22 on a real watch task ("Why the Best-Looking Websites Don't Sell",
11:31 video, openrouter vision credit-dead). Artifacts were in /tmp/watch/.

## Why MHTML storyboards

ffmpeg's tile output as `.mhtml` embeds every grid cell as an individual full-quality JPEG,
unlike `.jpg` tiles which bake cells into one image you must blind-crop. Parsing:

```python
import email, email.policy, io
from PIL import Image

msg = email.message_from_bytes(open('storyboard.mhtml','rb').read(), policy=email.policy.default)
cells = []
for part in msg.walk():
    if part.get_content_type() == 'image/jpeg':
        im = Image.open(io.BytesIO(part.get_payload(decode=True)))
        W, H = im.size
        cw, ch = W // cols, H // rows          # e.g. 320x180 for 6x5 of 1920x1080... check actual
        for y in range(0, H - ch + 1, ch):
            for x in range(0, W - cw + 1, cw):
                c = im.crop((x, y, x + cw, y + ch))
                # dedupe: near-black/blank filler cells have almost no distinct colors at 8x5
                if len(set(list(c.resize((8, 5)).getdata()))) > 3:
                    cells.append(c)

# timestamp mapping: cell i covers t = duration * i / len(cells)
```

Generate multiple tiers in one ffmpeg pass each (scene threshold ~0.25-0.35):
- coarse: `scale=320:180,tile=3x2` (~6 frames, chapter-level)
- medium: `tile=10x14` (~140 frames, ~one per 5s on a 12min video)
- thumbnail: `yt-dlp` already fetched `maxresdefault.jpg` — always the single most reliable image for moondream.

## Ollama vision helper (REST, not CLI)

CLI `ollama run moondream "prompt" img.jpg` mangles the path into the prompt. Use the API:

```python
import json, base64, urllib.request

def see(path_or_bytes, prompt, timeout=240):
    b = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes,'rb').read()
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate',
        data=json.dumps({'model': 'moondream', 'prompt': prompt, 'images': [base64.b64encode(b).decode()],
                         'stream': False, 'options': {'num_predict': 400, 'temperature': 0.15}}).encode(),
        headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())['response'].strip()
```

## Reliability findings (moondream, small model)

| Input | Result |
|---|---|
| Hi-res thumbnail (1280x720) | Excellent — reads overlay text verbatim, describes layout/people/colors |
| Native 320x180 storyboard cell | Often empty response |
| LANCZOS upscale 160x90 → 640x360 | Sometimes good, often empty or one-word garbage |
| Contact sheet / grid (any size) | FLAKY: worked once on 1920x810 half-grid, then returned empty on rerun; busy grids produce hallucinated counting sequences ("0 1 2 3 ... 99") |

Rules:
1. One frame per call. Grid answers that do come back are worth having, but never depend on them.
2. Empty string = retry once with simpler prompt; then move on.
3. Garbage detector: responses that are punctuation soup, number sequences, or <5 chars → treat as empty.
4. Batch sequentially with `flush=True` prints so partial progress survives timeouts.
5. Check `ollama list` BEFORE pulling anything — models sit there pre-pulled more often than expected.

## Companion-article trick

Creator videos almost always have a companion blog post (link usually in description) carrying
the same charts and statistics at full resolution WITH named sources (study names, authors).
When storyboard cells are unreadable but the video is data-heavy, fetching that article
legitimately recovers the entire data-visual channel — often better sourced than squinting at frames.

## Report format

Cover: metadata (title/channel/duration/views), argument chapter by chapter from transcript,
verified receipts (numbers + sources), then implications relevant to the user's own projects.
Always state coverage honestly: "audio channel 100% (verbatim transcript); visual channel partial
(thumbnail hi-res read, N keyframes decoded, charts recovered via companion article)".
