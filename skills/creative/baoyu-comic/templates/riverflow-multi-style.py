#!/usr/bin/env python3
"""Multi-style comic generator using sourceful/riverflow-v2.5-pro:free
Generates N styles x 15 pages = 15*N images, same story each variant.

Working pattern validated: 341/345 images generated successfully.
21:9 ultrawide may fail with HTTP 500 - add "ultrawide" to prompt or use 1920x1080.
"""

import json, base64, os, subprocess, tempfile, time

# Extract key from hermes config
with open('/home/alca/.hermes/config.yaml', 'rb') as f:
    d = f.read()
i = d.find(b'openddeepseek:')
if i < 0: i = d.find(b'opendeepseek:')
s = d[i:i+200]
a = s.find(b'api_key:')
KEY = s[a+9:a+82].decode('ascii')

OUT = 'outputs'  # Relative to comic directory

CHARACTERS = """THE ARCHITECT: 30s engineer, teal jacket, amber HUD wrist-terminal.
THE SYSTEM: luminous, teal lattice hair, 204k+ nodes.
DREAM ENGINE: 7-phase sphere. ALL text rendered. Ultrawide 21:9."""

def gen_page(style_desc, page_text, outpath):
    prompt = CHARACTERS + f" Style: {style_desc}. {page_text}. Ultrawide 21:9."
    body = json.dumps({
        "model": "sourceful/riverflow-v2.5-pro:free",
        "reasoning": {"effort": "high"},
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000
    })
    pf = tempfile.mktemp(suffix='.json')
    rf = tempfile.mktemp(suffix='.json')
    with open(pf, 'w') as f: f.write(body)
    hdr = 'Authorization: ' + 'Bearer ' + KEY
    subprocess.run(['curl', '-s', '--max-time', '420', '-H', hdr, '-H', 'Content-Type: application/json', '-d', '@' + pf, 'https://openrouter.ai/api/v1/chat/completions', '-o', rf], capture_output=True, text=True, timeout=480)
    os.unlink(pf)
    time.sleep(1)
    try:
        with open(rf) as f: data = json.load(f)
        os.unlink(rf)
        imgs = data.get('choices',[{}])[0].get('message',{}).get('images',[])
        if imgs:
            url = imgs[0]['image_url']['url']
            if url.startswith('data:'):
                with open(outpath, 'wb') as f: f.write(base64.b64decode(url.split(',',1)[1]))
                return True
    except Exception as e:
        print(f"Error: {e}")
        if os.path.exists(rf): os.unlink(rf)
    return False

# Usage: Populate STYLES and PAGES lists, then loop
# for i, style in enumerate(STYLES, 1):
#     style_dir = os.path.join(OUT, f'style_{i:02d}')
#     os.makedirs(style_dir, exist_ok=True)
#     for j, page in enumerate(PAGES):
#         if gen_page(style, page, os.path.join(style_dir, f'{j:02d}.webp')):
#             print(f'OK style_{i:02d}/{j:02d}')
#         time.sleep(2)