# Decode an inline-SVG QR from a pairing HTML page

When a gateway serves pairing at `https://host:port/pair`, it returns an HTML page
whose embedded QR is an inline `<svg>` (no `<img>`, no data-URI, no PNG on disk).
The `.code` block on the page may show a MASKED/truncated value (e.g. `eyJ2Ij...eSJ9`)
for UI display — that string is NOT the full payload and cannot be base64-decoded.

The real payload is only in the SVG's black modules. Recipe (proven 2026-08-07):

## 1. Fetch the HTML (retry; the gateway can be flaky under parallel curl)

```bash
for i in 1 2 3; do
  curl -sk --retry 2 --connect-timeout 5 -o /tmp/pair.html https://127.0.0.1:8443/pair \
    && break; sleep 2
done
wc -c /tmp/pair.html
```

## 2. Render the SVG QR to a PBM and decode with zbarimg

```python
import re
html = open('/tmp/pair.html').read()
# Every black module is a <rect x= y= width=1 height=1 fill="#000000">
rects = re.findall(r'<rect x="(\d+)" y="(\d+)" width="1" height="1" fill="#000000"', html)
# 57x57 in this gateway's output — derive bounds from the rects instead of assuming
s = 10  # scale factor so zbarimg can read it
w = h = max(max(int(x) for x, _ in rects), max(int(y) for _, y in rects)) + 1
pixels = {(int(x), int(y)) for x, y in rects}
lines = []
for yy in range(h):
    row = ''.join('1' if (xx, yy) in pixels else '0' for xx in range(w))
    for _ in range(s):
        lines.append(row.replace('0', '0'*s).replace('1', '1'*s))
open('/tmp/qr.pbm', 'w').write(f'P1\n{w*s} {h*s}\n' + '\n'.join(lines) + '\n')
```

```bash
zbarimg -q /tmp/qr.pbm          # → QR-Code:eyJ2Ij...  (the FULL payload)
```

## 3. Decode the payload

```bash
zbarimg -q /tmp/qr.pbm 2>/dev/null | sed 's/^QR-Code://' | \
  python3 -c "import sys,base64,json; raw=sys.stdin.read().strip(); print(json.dumps(json.loads(base64.b64decode(raw)), indent=2))"
```

## Alternative: /pair.json if the gateway offers it

Some gateways serve `/pair.json` returning `{"code": "...", "fp": "..."}` with the
UNMASKED code — try that first; it avoids the whole SVG dance.

```bash
curl -sk https://127.0.0.1:8443/pair.json | python3 -c "import sys,json; print(json.load(sys.stdin)['code'])"
```

## Notes

- `exit 56` from curl = network receive error; retry with `--retry` and a sleep.
- zbarimg must be installed (`/usr/bin/zbarimg`); pyzbar/qrcode Python bindings are
  often absent — PBM + zbarimg needs no pip installs.
