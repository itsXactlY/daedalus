# Cinematic Impact Layers — drone bed + risers + Qwen3-TTS `instruct`

Session source: 2026-06-19, mazemaker-trailer-2m32 (152s, brand climax at 2:17.5).

For cinematic trailers that need to **land** at specific timestamps (a stat
that drops, a bar that breaks, a logo that appears), the per-VO deluxe
chain is not enough. You also need a low drone bed underneath the whole
score window + a single white-noise riser telegraphing each impact moment
+ a sub-bass pulse right on the beat.

## Drone bed (continuous low sub under the music window)

A two-sine stack (a fifth apart) with tremolo + lowpass, placed at the
score window start. The operator stays in the audience's body even when
the music drops out between VO lines.

```bash
ffmpeg -y -f lavfi -i sine=f=42:d=$SCORE_LEN \
       -f lavfi -i sine=f=63:d=$SCORE_LEN \
       -filter_complex "[0][1]amix=2,tremolo=f=0.12:d=0.4,lowpass=f=120,volume=0.30,
                        aresample=48000,aformat=channel_layouts=stereo,
                        adelay=$SCORE_IN_MS|$SCORE_IN_MS,apad=whole_dur=$RUNTIME" \
       -t $RUNTIME -ar 48000 -ac 2 drone.wav
```

- 42Hz + 63Hz = a perfect fifth below the bed (a fifth above feels too
  bright, a fourth below muddies the music).
- `tremolo=0.12:0.4` gives a slow 0.12Hz amplitude modulation at 0.4 depth
  — feels like the drone is breathing, not a static hum.
- `lowpass=f=120` keeps the drone BELOW the bed's 60Hz body shelf so
  they don't fight; the bed's body fill comes from the score itself.
- `volume=0.30` is enough to be felt in headphones, won't show up on
  a volumedetect as a peak (it's all sustained low energy).
- Place it on the SCORE_IN timestamp, NOT at t=0 — the cold open is
  silence, the drone entering with the music reinforces the moment.

## Riser (white-noise sweep into the impact moment)

0.4-1.6s of bandpassed white noise, sweeping from a low center freq to a
high center freq. Place it 0.4-0.8s BEFORE the impact moment so the
audience's ear has a rising tension to release.

```bash
# At t=89.0s (1.4s, sweeping 600→2800Hz, gain 0.6) — telegraphing the
# "Eighty" wall-break at 1:30.4 (t=90.4s)
ffmpeg -y -f lavfi -i anoisesrc=d=1.4:c=white:a=1.0:r=48000 -af \
  "highpass=f=300,bandpass=f=600:width_type=q:w=0.7,afade=t=in:st=0:d=1.4,
   volume=0.6,aresample=48000,aformat=channel_layouts=stereo,
   adelay=${AT_MS}|${AT_MS},apad=whole_dur=$RUNTIME" \
  -t $RUNTIME -ar 48000 -ac 2 riser.wav
```

- The 0.4-0.8s gap between riser-end and impact-onset is the *breath*
  before the punch. Too tight and it feels like a single sound; too
  long and it loses tension.
- Two impacts = two risers. Don't overdo it — the absence of a riser
  makes the moments that DO have one land harder.
- For the "Eighty" wall-break: riser peak lands 0.4s before the word
  hits, so audience attention is already high when the number drops.

## Sub-bass pulse (right on the impact beat)

Same as the brand climax sub (32Hz sine, lowpassed at 80Hz), but placed
right on the impact moment, not 0.2s before. The riser primes the
audience, the sub delivers the physical sensation.

```bash
# At t=90.2s (just AFTER "Eighty" lands at 90.4s — 200ms after, the
# sub kicks when the word's consonant energy dies down)
ffmpeg -y -f lavfi -i sine=f=32:d=2.4 -af \
  "afade=t=out:st=0.05:d=2.35,lowpass=f=80,volume=1.0,
   aresample=48000,aformat=channel_layouts=stereo,
   adelay=90200|90200,apad=whole_dur=$RUNTIME" \
  -t $RUNTIME -ar 48000 -ac 2 sub_wall.wav
```

Verify the sub is in the actual mix:

```bash
ffmpeg -ss 89.5 -t 2 -i trailer.mp4 \
  -af "highpass=f=20,lowpass=f=80,volumedetect" -f null - 2>&1 | grep max_volume
# Should be > -40 dB in the 32-80Hz band at the riser/sub window.
```

## Qwen3-TTS `instruct` parameter — per-line tone control

The Qwen3-TTS `generate_custom_voice()` function accepts an `instruct`
parameter (string) that guides tone, emotion, pace, and register. This
is the single biggest lever for making a multi-line VO feel like a
DIRECTED performance rather than 32 random TTS samples.

```python
wavs, sr = m.generate_custom_voice(
    text="Every AI you have ever spoken to… forgets you.",
    speaker="aiden",
    language="English",
    non_streaming_mode=True,
    temperature=0.55,                    # lower = more controlled/cinematic
    top_p=0.85,
    max_new_tokens=4096,
    instruct="Speak in a cold, low whisper, like an intimate accusation.",
)
```

The `instruct` does NOT appear in the audio — it's only a prompt to the
TTS model. So you can write it as a director's note, not as in-fiction
text.

Effective instruct patterns for cinematic VO:

| Mood              | Instruct pattern                                            |
|-------------------|-------------------------------------------------------------|
| Cold / accusatory | "Speak in a cold, low whisper, like an intimate accusation." |
| Flat / clinical   | "Flat and clinical, as if reading a verdict."                |
| Slow / weighted   | "Slow, deliberate. Let the word 'X' land heavily."           |
| Hushed wonder     | "Hushed wonder, almost tender."                             |
| Certain / final   | "Certain. Final on the last word."                          |
| Calm authority    | "Calm authority over the stat. The number breathes."         |
| Reverent / quiet  | "Quiet. Reverent. Don't oversell."                           |
| Near-whisper out  | "Final line in a near-whisper. Out."                         |

**Tone arc**: design the `instruct` so it tracks the emotional curve of
the script. Cold open → flat → weighted → hushed → certain → calm
authority → reverent → near-whisper out. Don't write 32 different
instructs that all say "say this with feeling" — write a small library
of mood-markers and reuse.

**Temperature**: for cinematic VO, drop from the default 0.7 down to
**0.5-0.6**. Higher temperature = more expressive variation = more
mush-mouth artifacts. Lower = cleaner articulation, less variation
between takes.

**Speakers available** in Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice:
`['aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee',
'uncle_fu', 'vivian']`. Aiden is the male/neutral default we've used
consistently. For deeper/more cinematic VO, also test `dylan` and
`eric` — they read male, slightly different registers.

## Qwen3-TTS package location gotcha (2026-06-19)

The original `~/comfy/ComfyUI/custom_nodes/ComfyUI-Qwen-TTS` node was
removed. The official Qwen3-TTS package is at:
`https://github.com/QwenLM/Qwen3-TTS`

Usage from a fresh install:

```python
import sys
sys.path.insert(0, "/home/alca/comfy/ComfyUI/custom_nodes/Qwen3-TTS")
from qwen_tts import Qwen3TTSModel
import torch
m = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation="sdpa",  # not "flash_attention_2" unless installed
)
```

The model weights cache at `~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/`
(4.3GB on disk). Use `huggingface_hub.snapshot_download(allow_patterns=["*.json","*.txt","*.safetensors","*.py"])`
to pre-fetch if needed.
