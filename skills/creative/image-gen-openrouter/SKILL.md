---
name: image-gen-openrouter
description: "Generate images via OpenRouter's chat/vision models that support native image output (text+image->text+image). REQUIRES EXPLICIT USER OPT-IN PER SESSION (operator standing rule: do not silently burn OpenRouter credits). Use only after confirming the user has authorized OpenRouter spending in the current turn."
version: 1.2.0
author: daedalus
license: MIT
platforms: [linux, macos, windows]
metadata:
  daedalus:
    tags: [image-generation, openrouter, fallback, vision-models, text-to-image, creative, opt-in-required]
    category: creative
---

# Image Generation via OpenRouter Chat Models

Generate images when `image_generate` (FAL) is unavailable and local ComfyUI is not an option. Uses OpenRouter's chat models that output images natively (modality: `text+image->text+image`).

## MANDATORY: Operator Opt-In Required

Do NOT silently choose this skill as a fallback. The operator has a hard standing rule against burning OpenRouter credits without explicit authorization in the current turn.

Before calling any OpenRouter endpoint from this skill, the agent MUST confirm in the current conversation that the user has explicitly authorized OpenRouter image generation. Acceptable forms: "Use OpenRouter for this image", "go ahead, use OpenRouter", "credits are fine, generate it", or explicit acknowledgment when the agent surfaces the cost estimate.

If the user has not authorized it, DO NOT call OpenRouter. Fail honestly and pivot to ASCII art, HuggingFace free, or FAL if key is available. Real cost is ~$0.05–0.10 per image for chat-based image models, not the deceptive $0.000003 token math.

## When to Use (with opt-in)

- User has explicitly authorized OpenRouter image generation in the current turn
- `image_generate` (FAL) is unavailable AND local ComfyUI is not an option
- User explicitly wants OpenRouter-based generation
- User needs good text rendering in generated images (comics, infographics with labels)
- User specified a free tier and you need the cheapest viable option

## Prerequisites

- `OPENROUTER_API_KEY` set in `~/.daedalus/.env` or `~/.config/daedalus/.env`
- OpenRouter account
- `curl` available or Python's `subprocess` + `urllib`

## How It Works

OpenRouter does not serve traditional image generation models. Instead, it routes chat models that can output images natively (modality `text+image->text+image`).

```bash
source ~/.daedalus/.env 2>/dev/null
curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
for m in d.get('data',[]):
    mod = m.get('architecture',{}).get('modality','')
    if '->text+image' in mod or '->image' in mod:
        p = m.get('pricing',{})
        print(f\"{m['id']} | prompt=\${p.get('prompt','?')} | completion=\${p.get('completion','?')}\")"
```

## Known Image-Output Models (as of 2026-06)

| Model | Cost | Notes |
|---|---|---|
| `sourceful/riverflow-v2.5-pro:free` | DEAD | Returns HTTP 404 since 2026-06-13. Use paid version or Gemini Flash instead. |
| `google/gemini-3.1-flash-image-preview` | ~$0.07/image | Primary fallback, 1376x768, ~11-19s |
| `google/gemini-3-pro-image-preview` | very cheap | Best text rendering |
| `google/gemini-2.5-flash-image` | very cheap | Fast |
| `openai/gpt-5-image-mini` | very cheap | Up to 4K |
| `openai/gpt-5.4-image-2` | very cheap | Excellent text rendering |
| `openai/gpt-5-image` | very cheap | Best for comic text |

Cost is real $0.05-0.10/image because image-output models encode the image as base64 in output tokens. A 2MB image is ~2.6M completion tokens. Assume $0.05-0.10 per image. A 15-page comic costs ~$0.75-$1.50.

## Response Format

Both Gemini and Riverflow return images in `message.images[].image_url.url`. Always check `images[]` first, not `content`. Set `max_tokens` to 4000-8000 for full-quality output.

Gemini 3.1 Flash Image outputs at fixed 1376x768 despite prompt requests for higher. Do not over-specify resolution.

```python
import urllib.request, json, base64

payload = json.dumps({
    "model": "google/gemini-3.1-flash-image-preview",
    "messages": [{"role": "user", "content": "Your prompt here."}],
    "max_tokens": 8000
}).encode()

req = urllib.request.Request(
    'https://openrouter.ai/api/v1/chat/completions',
    data=payload,
    headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req, timeout=300) as resp:
    d = json.loads(resp.read())

images = d['choices'][0]['message'].get('images', [])
if images:
    url = images[0]['image_url']['url']
    if url.startswith('data:'):
        _, b64 = url.split(',', 1)
        with open('/path/to/output.webp', 'wb') as f:
            f.write(base64.b64decode(b64))
```

## Reasoning Parameter (Riverflow)

For Riverflow models: `"reasoning": {"effort": "xhigh"}` (object, NOT string). String value causes HTTP 400.

## Cross-Page Consistency

For multi-page comics, prepend a shared style preamble to every page prompt: narrative summary, character definitions with hex colors, visual constants, current page position.

For comics prioritize STORY over text density. Say "manga comic strip with proper panel layouts, character dialogue in oval speech bubbles" not "MAXIMUM TEXT". Characters must DO things, not stand and explain.

## Decision Tree (opt-in gated)

```
image needed?
├── FAL_KEY set? → image_generate tool (FAL flux/schnell)
├── User EXPLICITLY authorized OpenRouter this turn?
│   ├── YES → google/gemini-3.1-flash-image-preview (~$0.07/image)
│   └── NO → ASK before any spend. If declined, fall through.
├── Local GPU + ComfyUI running? → creative:comfyui
├── Free path needed? → HuggingFace free inference API (FLUX.1-schnell)
└── Nothing else works? → creative:ascii-art
```

Default on this operator's machine: FAL → ask before OpenRouter → ASCII fallback. Never silently select OpenRouter.

## Pitfalls

1. Riverflow free is DEAD as of 2026-06-13
2. Model availability changes - re-query /v1/models before relying on a specific ID
3. Base64 data URLs - save to file immediately
4. max_tokens matters - set 4000-8000 for image outputs
5. Gemini 3.1 Flash outputs at 1376x768 fixed
6. Images in `message.images[]` not `message.content`
7. Python 3.14 http.client uses `body=` not `data=`
8. Real cost $0.05-0.10/image not the naive token math
9. No /api/v1/images/generations endpoint - use chat completions

## Related Skills

- `creative/comfyui` - Local GPU image generation
- `image_generate` tool - FAL-based
- `creative/baoyu-comic` - Knowledge comics
- `creative/baoyu-infographic` - Infographics