# 100+ Iterations Pattern — "Director's Cut" Trailers Assembled From Existing Assets

A pattern for the class of work where a trailer is a **re-cut** of pre-existing
material: voiceover WAVs, a generated score, hero stills from a multi-style
comic, and a short narrative script. The deliverable is a single self-contained
HTML file that hits 100+ kinetic moments without generating a single new image
or recording a single new audio sample.

## When to use this pattern

- The narrative is already written (script exists, VO already generated)
- The visual library already exists (multi-style comic renders, hero plates)
- The score already exists (a strudel/midi render, MusicGen output, or stock cue)
- The brief asks for "director's cut", "ultimate assembly", "definitive trailer",
  "100+ moments", or similar — i.e. the work is curation + pacing, not generation

If any of the three assets is missing, fall back to Pipeline A or B in the parent
skill (Flux → Cosmos Predict2 → Resolve, or Flux → HTML/CSS) and generate first.

## Density math (worked example from a live session)

Runtime: 107s · 6 acts · 16 VOs · 1 score · 53 SFX · **209 total iterations**

| Act | t-range | dur | VO | kinetic | motif | hero | terminal | flash | SFX | sub-total |
|-----|---------|-----|----|---------|-------|------|----------|-------|-----|-----------|
| 0  | 0–9s    | 9s  | 1  | 15      | 1     | 0    | 0        | 1     | 3   | ~21       |
| 1  | 9–22s   | 13s | 3  | 15      | 0     | 0    | 0        | 2     | 6   | ~26       |
| 2  | 22–40s  | 18s | 2  | 22      | 1     | 0    | 0        | 2     | 12  | ~39       |
| 3  | 40–55s  | 15s | 3  | 11      | 0     | 2    | 0        | 2     | 9   | ~27       |
| 4  | 55–75s  | 20s | 2  | 14      | 1     | 2    | 1        | 1     | 14  | ~35       |
| 5  | 75–93s  | 18s | 2  | 15      | 0     | 1    | 0        | 6     | 9   | ~33       |
| 6  | 93–107s | 14s | 1  | 9       | 0     | 1    | 0        | 1     | 4   | ~16       |
| **TOTAL** |   | 107s | 16 | **99** | **4** | **6** | **2** | **14** | **53** | **197** |

Plus chrome lower-thirds (3) and act counters (7) = 209. The "iterations"
metric the user asked for is satisfied by 100+ visual + 50+ SFX = 150+
discrete punch-ins. Anything past 100 is past the threshold.

### Density targets per act

- ACT 0 (cold open): ~1 kinetic/second · silence · one motif seed
- ACT 1 (diagnosis): ~1.2 kinetic/second · low rumble · staccato words
- ACT 2 (the nature): ~1.2 kinetic/second · music enters · 5-fold word staccato
- ACT 3 (the demo): ~0.7 kinetic/second · hero plates · chrome lower-thirds
- ACT 4 (climax): ~0.7 kinetic/second · terminal panel · biggest visual moment
- ACT 5 (the turn): ~0.8 kinetic/second · lots of strikes
- ACT 6 (the brand): ~0.6 kinetic/second · slowing · final logo

The peak density is in the middle (act 2). The bookends are paced for
inhalation/exhalation. Don't try to fill 1.5 elements/second in act 0 — the
cold open needs silence to land.

## Asset assembly

Required inputs:

1. **16 narrator voiceover segments** (Qwen3-TTS, Aiden, or similar)
   - Each segment is 1-15s, total ~88s of spoken narration
   - Stored as WAV in `voiceover_uprising/vo_NN.wav`
   - Scheduled via a `VOS` dict: `{1:['vo01', startTime], ...}`

2. **1 orchestral score** (~100s, 48kHz WAV/FLAC)
   - Pizzicato ostinato, dread pads, cello sighs, taiko, shakuhachi solo
   - Fades in around t=20s, fades out around t=92s
   - Generated via strudel/fluidsynth from a `compose_*.py` MIDI script

3. **6-8 hero stills** (cyberpunk_neon/04, neural_network_glow/07, etc.)
   - Each is ~150-250KB webp from a multi-style comic generation
   - Used as full-screen backplates for 2-4s windows each
   - Chosen for visual variety (different palette, different subject)

4. **The script** (segmented into the 16 VO lines)
   - Each line has natural staccato word boundaries
   - The 5-fold and 6-fold repetitions are the spine of the 100+ count

## File structure

```
directors-cut/
├── index.html              ← the deliverable (49KB)
├── README.md
├── director-notes.md       ← shot-by-shot breakdown
├── assets/                 ← 6 hero stills
├── vo/                     ← 16 VOs (symlinked from voiceover_uprising/)
└── score/                  ← score WAV (symlinked)
```

Symlinks keep the re-cut lean — a 49KB HTML plus 1.3MB of assets, no duplication
of the 200MB+ source material.

## Implementation checklist

- [ ] Pick the 6-8 hero stills that span the 6 acts visually
- [ ] Schedule the 16 VOs to start at sensible cue points (each VO needs
      visual material to play over, not just black)
- [ ] Schedule SFX peaks 0.5-0.8s after the VO's emotional word, not on the VO start
- [ ] Score in at t=20-22s (after the cold open and the diagnosis), out at t=90-93s
- [ ] Add a "word-motif" pulse 3-4 times across the runtime (the word that names
      the brand's territory — here "uplanning", but in general the verb-noun
      that IS the product)
- [ ] Act counter overlays (TL, mono) at the start of each act
- [ ] Chrome lower-third at the demo moment (e.g. "CLAUDE CODE · MONDAY")
- [ ] One terminal panel mid-trailer (proof of concept — show the actual data)
- [ ] Final logo (no kinetic text, just the mark) for the last 4-5s
- [ ] Total iterations counted from `liveEls.length + SFX.length + audioElements.length`

## Verification (post-build)

Static checks (no browser needed):
- `python3 -c "import re; s=open('index.html').read(); m=re.search(r'<script>(.*?)</script>',s,re.DOTALL); open('/tmp/t.js','w').write(m.group(1))"`
- `node --check /tmp/t.js` — must pass with no errors
- `grep -c "kinetic(" index.html` — count kinetic text moments
- `grep -cE "^  \[" index.html` — count SFX cues
- HTTP 200 on all `<audio src>` and `<background-image url>` paths

Visual checks (browser needed):
- Open `?autostart=1` and watch the full 107s
- Open `?time=3`, `?time=22`, `?time=70`, `?time=106` to spot-check key moments
- The final logo should hold for at least 3s with no kinetic text overlay

## Re-cut vs. Pipeline B (Flux → HTML/CSS) — when to choose which

| Signal | Re-cut (this pattern) | Pipeline B |
|--------|----------------------|------------|
| Source material exists | YES | NO |
| Brand new cinematic brief | NO | YES |
| Image generation in budget | NO (use existing) | YES |
| "Ultimate/director's/definitive" framing | YES | sometimes |
| Fresh product launch | NO | YES |
| Aggregate existing assets into one piece | YES | NO |

The 6-act viral architecture in the parent skill is the same in both. The
difference is: re-cut pulls from a library, Pipeline B generates fresh.

## Variant: voiceover out (pure visual + score + SFX)

Some briefs explicitly require no voiceover: "sämtliches voiceover muss
raus" / "voiceover out" / "drop the narration". The change is surgical,
not architectural — same OOP classes, same scene system, just remove the
VO plumbing and compensate the iteration count.

**Remove from `trailer.js`:**
- The `VOICE_CUES` array (16 entries)
- `AudioEngine.playVoice(id)` method
- `AudioEngine.loadVoices(cues)` method
- `AudioEngine.#voices` Map field
- `Trailer.#countActiveVoices()` helper
- The `for (const cue of VOICE_CUES)` loop in `Trailer.#buildAudioSchedule()`

**Remove from `index.html`:**
- All 16 `<audio id="vo01" ... vo16">` elements
- The `XX/16 VO` substring in the debug overlay

**Keep:**
- The score audio element (the only audio source now)
- The `vo/vo_NN.wav` files on disk (archive; the symlinks remain so the
  files can still be HTTP-served if asked, but no `<audio>` references
  them so the browser doesn't auto-load them)
- The kinetic typography that quoted the VO text (the words still appear
  on screen — they're visual story, not voiceover)

**Compensate for the dropped iteration count:**
Voiceover contributed 16 to the iteration count. To stay ≥300 after removal,
add 20-30 more scenes. Easiest place: per-word staccato on the cold open
("Y/O/U/R" each as its own 0.3s kinetic), repeated motif echoes (`gone.`
three times in 1s), date stamps (`mon. 04.06.` / `thu. 04.10.`) at the
demo moment. Distributed across all 6 acts, ~5 scenes per act = 30
additional.

**Final iteration formula (no voiceover):**
```
total = scene_count + sfx_count + 1   # +1 for the score
```

The `scripts/cdp-validate.py` "Voiceover fully removed" check verifies
zero `VOICE_CUES` / `playVoice` / `loadVoices` / `countActiveVoices` in
JS and zero `<audio id=vo*>` in HTML — a hard guardrail against
re-introduction. Add this check whenever the no-voiceover constraint is
active.

**Live worked example (no voiceover):** 241 scenes + 79 SFX + 1 score
= 321 iterations, 14/14 hard checks pass, t=105s shows the gold
MAZEMAKER finale, no console exceptions, AudioContext state = 'running'.
