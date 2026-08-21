# Deluxe Mastering Recipe — Beyond film_a_

Session source: 2026-06-19, mazemaker-trailer-deluxe (137s, peak at 2:17).

The standard `film_a_` recipe in the main SKILL.md gets the voice audible.
This reference covers when the trailer has to **land** — brand climax at a
specific timestamp, peak cinematic impact, trailer-grade loudness without
mangling the voice or breaking the canonical duck invariant.

## A/B delta vs film_a_

Single-VO test under identical conditions (one Qwen-TTS line at t=29s, same
bed segment, same sidechain params):

| Metric                | film_a_ baseline | deluxe single-VO | Delta      |
|-----------------------|------------------|------------------|------------|
| Voice peak            | -16.6 dB         | -10.2 dB         | **+6.4 dB**|
| Voice mean            | -30.8 dB         | -23.3 dB         | **+7.5 dB**|
| Integrated loudness   | -30.6 LUFS       | -22.1 LUFS       | **+8.5 LU**|
| True peak             | -16.6 dBTP       | -10.2 dBTP       | +6.4 dB    |

Full trailer (137s, 16 VOs): mean -22.6 dB, max -4.2 dB, integrated -20.3
LUFS, true peak -4.2 dBTP. Voice rides clearly on top of the ducked music
bed. Sub-bass confirmed in 32-80Hz band at the 2:17 mark.

## Per-VO deluxe chain

Applied to each Qwen3-TTS line BEFORE placement on the timeline:

```bash
af = ("highpass=f=70,"
      "afftdn=nf=-25,"
      "acompressor=threshold=-22dB:ratio=2.5:attack=8:release=120:makeup=1,"
      "equalizer=f=3500:width_type=q:w=1.2:g=1.5,"      # presence +1.5dB
      "equalizer=f=6500:width_type=q:w=1.5:g=-2,"       # de-ess -2dB
      "aecho=0.7:0.6:60:0.4,"                            # tiny room 60ms, 0.4 wet
      "aresample=48000,aformat=channel_layouts=stereo,"
      "afade=t=in:st=0:d=0.08,adelay=$MS|$MS,apad=whole_dur=$RUNTIME")
```

Notes:
- `makeup=1` is the minimum, NOT 0. See main SKILL Pitfall 9.
- `aecho` parameters are `in_gain:out_gain:delay_ms:decay`. With 60ms
  delay and 0.4 decay it's a barely-there room — too much and the voice
  sounds like it's in a tiled bathroom.
- Skip `aecho` if the bed is at -22 LUFS or louder — the room kills
  intelligibility at higher bed levels.

## Score bed deluxe (replaces the simple `loudnorm=I=-30,volume=0.9`)

```bash
af = ("aresample=48000,aformat=channel_layouts=stereo,atrim=0:$SEG,"
      "equalizer=f=60:width_type=q:w=0.7:g=2,"           # low-end body
      "equalizer=f=8000:width_type=q:w=0.7:g=1.5,"       # air
      "acompressor=threshold=-18dB:ratio=2:attack=20:release=200,"  # glue
      "loudnorm=I=-22:TP=-2:LRA=11,"                    # louder than film's -30
      "stereowiden=delay=15:feedback=0.3:crossfeed=0.3:drymix=1.0,"
      "afade=t=in:st=0:d=1.5,afade=t=out:st=$SEG-0.5:d=0.5")
```

Why the bed moves from -30 (film ambient) to -22 (trailer-energy):
- The trailer needs to land. A bed at -30 is too quiet even after duck.
- The voice still rides on top because the duck compresses 8:1 on the bed.
- If you keep the bed at -30, the final mix comes out at -23 to -20 LUFS
  which is below trailer spec and feels under-cranked.

## Sub-bass impact layer (the brand climax)

A 32Hz sine, lowpassed at 80Hz, placed at impact moments. Use sparingly
— one pre-pulse during the build, one main pulse at the climax:

```bash
# t=85s (1.5s pre-pulse during the dream, gain 0.6) — build anticipation
# t=136.8s (2.4s climax at exactly 2:17, gain 1.1) — the brand moment
ffmpeg -y -f lavfi -i sine=f=32:d=2.4 \
  -af "afade=t=out:st=0.05:d=2.35,lowpass=f=80,volume=1.1,
       aresample=48000,aformat=channel_layouts=stereo,
       adelay=$MS|$MS,apad=whole_dur=$RUNTIME" ...
```

Verification that the sub is actually in the output:

```bash
ffmpeg -ss 135.5 -t 1.5 -i trailer.mp4 \
  -af "highpass=f=20,lowpass=f=80,volumedetect" -f null - 2>&1 | grep max_volume
# Audible sub: max > -40 dB in the 32-80Hz band at the brand timestamp.
```

## Final mix: VO + ducked bed + sub (with the asplit fix)

```bash
fc = ("[2:a][3:a]...[17:a]amix=inputs=16:normalize=0,volume=1.4,asplit=2[vosc][vomix];"
      "[1:a][vosc]sidechaincompress=threshold=0.04:ratio=8:attack=15:release=380[duck];"
      "[18:a][19:a]amix=inputs=2:normalize=0,volume=0.95[sub];"
      "[duck][vomix][sub]amix=inputs=3:weights=1 1 0.85:normalize=0,"
      "alimiter=limit=0.95,aresample=48000[a]")
```

The `asplit=2[vosc][vomix]` is the critical gotcha — see SKILL Pitfall 8.
Without it, the filter_complex fails with a misleading "Stream specifier
'vosc' matches no streams" error.

Input numbering convention (matters for the filter labels):
- 0 = video file (no audio, used as the mux anchor)
- 1 = score bed
- 2..(2+N-1) = N voiceover inputs
- (2+N)..end = sub-bass impacts

`vlabels` = `[2:a][3:a]...[N+1:a]`, `slabels` = `[N+2:a]...[N+M+1:a]`.

## Full 132-line build script

`/home/alca/comic/mazemaker-inception-os/v3/trailer/build_deluxe.py` is
the canonical deluxe build. Key constants and shape:

```python
RUNTIME   = 137.0                       # 2:17 - the peak
SCORE_IN  = 21.0;  SCORE_OUT = 113.0    # music bed window
PEAK      = 137.0                       # the brand climax moment
NVENC = ["-c:v","h264_nvenc","-preset","p6","-rc","vbr","-cq","19",
         "-b:v","24M","-maxrate","48M","-pix_fmt","yuv420p"]

VO_CUES = [                             # 16 Qwen-TTS lines, no overlap
    ("01",  5.0), ("02", 13.0), ("03", 17.5), ("04", 23.0), ("05", 29.0),
    ("06", 33.5), ("07", 45.0), ("08", 55.0), ("09", 58.5), ("10", 61.5),
    ("11", 66.0), ("12", 68.5), ("13", 84.5), ("14", 90.0), ("15",102.5), ("16",107.5) ]

HERO_PLATES = [...]                     # 6 ComfyUI plates, 40-113s

# Per-VO: dv(key, start) -> work/deluxe/dv_<key>.wav (137s padded)
# Bed:    ds()            -> work/deluxe/ds_bed.wav   (placed at 21-113s)
# Sub:    sub(at, dur, freq, gain) -> work/deluxe/sub_<at>.wav

# Subs: one pre-pulse + one climax pulse
subs = [sub(85.0, 1.5, 32.0, 0.6), sub(PEAK-0.2, 2.4, 32.0, 1.1)]
```

Total VO speech: 96.99s. 137s runtime gives the score + silence tail
+ sub-bass the room to land the brand climax at exactly 2:17 for
maximum cinematic impact.

To change runtime, set RUNTIME = new_value (line 14) and sil(54.0)
cold-open (line 103) such that `sil(D) + sum(hero plate durations) +
sil(2) + brand(12) = RUNTIME`.
