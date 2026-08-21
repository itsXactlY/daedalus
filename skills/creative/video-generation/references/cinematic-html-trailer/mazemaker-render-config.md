# MAZEMAKER-Specific Trailer Render Configuration

## 4K Render Script (adapted from render_4k.sh)

```bash
#!/bin/bash
# Mazemaker Trailer 4K Render
set -e

HTML="maze-crew-trailer.html"        # Current master trailer
OUTPUT="trailer-4k.mp4"
RES="3840x2160"
FPS="60"
CRF="16"
AUDIO="trailer-soundtrack.flac"
DURATION="46.2"                     # Must match END_AT in JS

cd /home/alca/projects/mazemaker-architect/public

# Xvfb + Chrome headless render
export DISPLAY=:99
Xvfb :99 -screen 0 ${RES}x24 &
XVFB_PID=$!

mkdir -p /tmp/chrome-trailer
google-chrome-stable --headless --new-window --no-first-run \
  --user-data-dir=/tmp/chrome-trailer \
  --window-size=3840,2160 \
  "file://$(pwd)/$HTML" &
CHROME_PID=$!

sleep 4
xdotool mousemove 1920 1080 click 1
sleep 0.5

ffmpeg -y -f x11grab -r $FPS -s $RES -i :99.0+0,0 \
  -i "$AUDIO" \
  -c:v libx264 -preset slow -crf $CRF -pix_fmt yuv420p \
  -c:a aac -b:a 320k -ar 48000 -ac 2 \
  -t $DURATION -movflags +faststart \
  "$OUTPUT"

kill $CHROME_PID $XVFB_PID 2>/dev/null
rm -rf /tmp/chrome-trailer
```

## Timing Verification

```javascript
// Add to startPlayback() or verify in animate loop
console.log('END_AT check:', END_AT, 'expected 46.2');
console.log('Score duration:', audio.duration, 'should match END_AT');
```

## Pitfall: Chrome Transition Behavior

CSS `transition-duration` on `#c` does NOT restart when bound to CSS variable. The animation interpolates smoothly. This is documented in cinematic-html-trailer Skill but verified in bio #21.

## Pitfall: Source vs Destination Amplitude

Phase-transition burst uses `Math.round(3 + _destSpeed * 4)` to scale pulse count by destination phase speed. Fast cinematic segments (spd 1.3-1.4) fire 8-9 pulses. Slow intimate dwells (spd 0.5-0.6) fire 5-6 pulses. See trailer #22 rationale.