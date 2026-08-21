#!/usr/bin/env python3
"""
RIVERFLOW BATCH GENERATOR — Template for multi-page comic generation
API key read via env var (never hardcoded). Resume-capable. Retry with backoff.

Usage:
  HERMES_RIVERFLOW_KEY=$(python3 -c "
    with open('/root/.hermes/config.yaml') as f:
      c = f.read(); i = c.find('opendeepseek:'); s = c[i:i+200]; k = s.find('api_key:');
      print(s[k+9:k+82].strip().strip(\"'\").strip('\"').strip())
  ") python3 this_script.py [slug_or_id]

Prerequisites:
  - Source file: output_dir/source-{slug}.md
  - Characters: output_dir/characters/characters.md
  - Storyboard: output_dir/storyboard.md
  - Prompts: output_dir/prompts/NN-{cover|page}-{slug}.md (15 files named 00-14)
"""

import json, base64, os, subprocess, tempfile, time, sys, traceback

# ─── CONFIG (edit these per run) ─────────────────────────────────────────
LOG_DIR = "./logs"                      # Where generation logs go
COMICS = [
    {
        "id": "01",                     # Short numeric ID
        "slug": "my-comic-slug",        # URL-safe slug
        "style": "art style description", # Full style prompt for the model
        "prompt_dir": "01-my-comic-dir"  # Directory relative to BASE
    },
    # Add more comics here...
]

BASE = "."  # Root directory containing the prompt_dir subdirectories
PAGE_TIMEOUT = 300  # Seconds per page (300 = 5 min for xhigh)
REASONING_EFFORT = "high"  # "high" or "xhigh"
MODEL = "sourceful/riverflow-v2.5-pro:free"
ASPECT = "16:9 landscape"  # Avoid 21:9 — causes HTTP 500

# ─── DO NOT EDIT BELOW ───────────────────────────────────────────────────

API_KEY = os.environ.get("HERMES_RIVERFLOW_KEY", "")
if not API_KEY:
    print("FATAL: Set HERMES_RIVERFLOW_KEY env var")
    sys.exit(1)

os.makedirs(LOG_DIR, exist_ok=True)


def get_page_prompts(comic_dir):
    """Get sorted list of prompt files from prompts/ subdir"""
    prompts_dir = os.path.join(comic_dir, "prompts")
    if os.path.isdir(prompts_dir):
        files = sorted(f for f in os.listdir(prompts_dir) if f.endswith('.md'))
        return [os.path.join(prompts_dir, f) for f in files]
    return []


def generate_page(prompt_text, style_desc, outpath, log_f, max_retries=2):
    """Generate one page. Returns True on success."""
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    full_prompt = f"{prompt_text}\n\nART STYLE: {style_desc}\nFormat: manga comic page, multi-panel layout, {ASPECT}, no baked text."

    for attempt in range(1, max_retries + 1):
        try:
            body = json.dumps({
                "model": MODEL,
                "reasoning": {"effort": REASONING_EFFORT},
                "messages": [{"role": "user", "content": full_prompt}],
                "max_tokens": 4000
            })

            payload_file = tempfile.mktemp(suffix='.json')
            with open(payload_file, 'w') as f:
                f.write(body)
            response_file = tempfile.mktemp(suffix='.json')

            auth_value = "Bearer " + API_KEY
            auth_hdr = "Authorization: " + auth_value

            start = time.time()
            result = subprocess.run(
                ["curl", "-s", "--max-time", str(PAGE_TIMEOUT),
                 "-H", "Content-Type: application/json",
                 "-H", auth_hdr,
                 "-d", "@" + payload_file,
                 "https://openrouter.ai/api/v1/chat/completions",
                 "-o", response_file],
                capture_output=True, text=True, timeout=PAGE_TIMEOUT + 20
            )
            elapsed = time.time() - start
            os.unlink(payload_file)

            if not os.path.exists(response_file):
                log_f.write(f"  Attempt {attempt}: No response (exit {result.returncode}, {elapsed:.0f}s)\n")
                log_f.flush()
                if attempt < max_retries: time.sleep(10)
                continue

            with open(response_file) as f:
                resp_data = f.read()
            os.unlink(response_file)

            if not resp_data.strip():
                log_f.write(f"  Attempt {attempt}: Empty ({elapsed:.0f}s)\n")
                log_f.flush()
                if attempt < max_retries: time.sleep(10)
                continue

            d = json.loads(resp_data)

            if 'error' in d and d['error']:
                err = str(d['error'])
                log_f.write(f"  Attempt {attempt}: {err[:200]} ({elapsed:.0f}s)\n")
                log_f.flush()
                if "429" in err or "rate" in err.lower():
                    time.sleep(30); continue
                if attempt < max_retries: time.sleep(10)
                continue

            images = d.get('choices', [{}])[0].get('message', {}).get('images', [])
            if images:
                url = images[0].get('image_url', {}).get('url', '')
                if url.startswith('data:'):
                    with open(outpath, 'wb') as f:
                        f.write(base64.b64decode(url.split(',', 1)[1]))
                    sz = os.path.getsize(outpath)
                    log_f.write(f"  OK: {os.path.basename(outpath)} ({sz}B, {elapsed:.0f}s)\n")
                    log_f.flush()
                    return True

            # Text fallback
            text = d['choices'][0]['message'].get('content', '')
            if text and len(text) > 100:
                log_f.write(f"  Attempt {attempt}: Text ({len(text)} chars, {elapsed:.0f}s)\n")
                log_f.flush()
                if attempt < max_retries: time.sleep(10)
                continue

            log_f.write(f"  Attempt {attempt}: No result ({elapsed:.0f}s)\n")
            log_f.flush()
            if attempt < max_retries: time.sleep(10)

        except subprocess.TimeoutExpired:
            log_f.write(f"  Attempt {attempt}: Timeout\n"); log_f.flush(); continue
        except Exception as e:
            log_f.write(f"  Attempt {attempt}: {e}\n"); log_f.flush()
            if attempt < max_retries: time.sleep(10); continue

    return False


def generate_comic(comic):
    """Generate all pages for one comic."""
    comic_dir = os.path.join(BASE, comic["prompt_dir"])
    outputs_dir = os.path.join(comic_dir, "outputs")
    log_path = os.path.join(LOG_DIR, f"{comic['id']}-{comic['slug']}.log")

    with open(log_path, 'w') as log_f:
        log_f.write(f"=== {comic['slug']} ===\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        log_f.flush()

        prompts = get_page_prompts(comic_dir)
        log_f.write(f"Found {len(prompts)} prompts\n\n"); log_f.flush()
        if not prompts:
            log_f.write("ERROR: No prompts\n"); return 0, []

        ok, fail = 0, []
        for i, pp in enumerate(prompts):
            base_name = os.path.basename(pp).replace('.md', '.webp')
            outpath = os.path.join(outputs_dir, f"{comic['id']}_{comic['slug']}_{base_name}")

            if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
                log_f.write(f"  SKIP: {base_name} ({os.path.getsize(outpath)}B)\n")
                log_f.flush(); ok += 1; continue

            log_f.write(f"\n[{i+1}/{len(prompts)}] {base_name}...\n"); log_f.flush()

            with open(pp) as f:
                text = f.read()

            if generate_page(text, comic["style"], outpath, log_f):
                ok += 1
            else:
                fail.append(base_name)
                log_f.write(f"  FAIL: {base_name}\n"); log_f.flush()

            if i < len(prompts) - 1:
                time.sleep(3)

        log_f.write(f"\nDONE: {ok}/{len(prompts)} pages\n")
        if fail: log_f.write(f"FAILED: {', '.join(fail)}\n")
    return ok, fail


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    total_ok, total_fail = 0, 0

    for comic in COMICS:
        if target and comic["id"] != target and comic["slug"] != target:
            continue
        print(f"\n--- [{comic['id']}] {comic['slug']} ---")
        start = time.time()
        ok, fail = generate_comic(comic)
        elapsed = time.time() - start
        total_ok += ok; total_fail += len(fail)
        print(f"  -> {ok} pgs ({elapsed/60:.0f} min)")
        if fail: print(f"  -> FAILS: {', '.join(fail)}")

    print(f"\nTOTAL: {total_ok} images")
