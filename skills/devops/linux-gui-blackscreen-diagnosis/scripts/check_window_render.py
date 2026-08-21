#!/usr/bin/env python3
"""check_window_render.py - objectively classify a GUI window as BLACKSCREEN vs RENDERED.

WHY: vision_analyze / multimodal models frequently HALLUCINATE on screenshots of
broken GUIs (seen: invented a "Google search / Vivaldi registration" page over a
Discord blackscreen). Pixel statistics are the ground truth. Use this instead.

USAGE:
  python3 check_window_render.py --class discord
  python3 check_window_render.py --geometry 1920x1033+0+47
  python3 check_window_render.py --class discord --screenshot /tmp/out.png   # analyze existing shot

REQUIRES: maim, xdotool (X11), Pillow (pip install pillow).
"""
import argparse, json, subprocess, sys, statistics, tempfile, os


def get_window_geom(wmclass):
    """Find all WIDs for class, return geometry of the LARGEST by area.
    Ignores 10x10 splash/hidden windows that share the class."""
    out = subprocess.run(["xdotool", "search", "--class", wmclass],
                         capture_output=True, text=True)
    wids = [w.strip() for w in out.stdout.split() if w.strip()]
    best = None
    best_area = 0
    for w in wids:
        g = subprocess.run(["xdotool", "getwindowgeometry", "--shell", w],
                           capture_output=True, text=True).stdout
        d = {}
        for line in g.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
        try:
            x = int(d["X"]); y = int(d["Y"]); ww = int(d["WIDTH"]); hh = int(d["HEIGHT"])
        except (KeyError, ValueError):
            continue
        area = ww * hh
        if area > best_area:
            best_area = area
            best = (x, y, ww, hh)
    return best


def analyze(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    px = im.load()
    w, h = im.size
    lums = [0.299 * px[x, y][0] + 0.587 * px[x, y][1] + 0.114 * px[x, y][2]
            for y in range(0, h, 10) for x in range(0, w, 10)]
    mean = statistics.mean(lums)
    sd = statistics.pstdev(lums)
    bright = sum(1 for l in lums if l > 120)
    black = sum(1 for l in lums if l < 15)
    n = len(lums)
    if sd < 8 and bright == 0:
        verdict = "BLACKSCREEN (flat void)"
    elif sd > 25:
        verdict = "RENDERED (real UI content)"
    else:
        verdict = "UNCLEAR"
    return {"mean_lum": round(mean, 2), "stdev": round(sd, 2),
            "bright": bright, "black": black, "total": n, "verdict": verdict}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="wmclass", help="WM class, e.g. discord")
    ap.add_argument("--geometry", help="WxH+X+Y capture region")
    ap.add_argument("--screenshot", help="analyze an existing PNG instead of capturing")
    args = ap.parse_args()

    if args.screenshot:
        path = args.screenshot
    else:
        if args.geometry:
            spec = args.geometry
        elif args.wmclass:
            geom = get_window_geom(args.wmclass)
            if not geom:
                print(json.dumps({"error": "no window found for class " + str(args.wmclass)}))
                sys.exit(2)
            x, y, w, h = geom
            spec = f"{w}x{h}+{x}+{y}"
        else:
            print(json.dumps({"error": "need --class, --geometry, or --screenshot"}))
            sys.exit(2)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        r = subprocess.run(["maim", "-u", "-g", spec, tmp], capture_output=True, text=True)
        if r.returncode != 0:
            print(json.dumps({"error": "maim failed", "stderr": r.stderr}))
            sys.exit(3)
        path = tmp

    res = analyze(path)
    print(json.dumps(res, indent=2))
    if path.startswith(tempfile.gettempdir()):
        os.remove(path)


if __name__ == "__main__":
    main()
