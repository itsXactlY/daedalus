# BTQuant Qwen Full Podcast Generation — Session Reference

## Exact Generation Command (June 8, 2026)

Run from session `20260608_155345_5d6bba`:

```python
import sys, os, time
sys.path.insert(0, '/home/alca/comfy/ComfyUI/custom_nodes/ComfyUI-Qwen-TTS')
from qwen_tts import Qwen3TTSModel
import numpy as np, wave

OUT = '/home/alca/comic/mazemaker-inception-os/v3/voice_btquant_podcast'
MODEL = 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'

model = Qwen3TTSModel.from_pretrained(MODEL)
speakers = model.get_supported_speakers()
spk1, spk2 = speakers[0], speakers[1]  # aiden, dylan
print(f'Speakers: {spk1}, {spk2}', flush=True)

remaining = [
    (7,  'S2', "The best strategy isn't the highest Sharpe. It's the one that sleeps through the night. Max drawdown point one five. Confidence threshold point seven two."),
    (8,  'S1', 'The market never sleeps. But we have to. Morning coffee. The machine worked while we dreamed.'),
    (9,  'S2', "All you have is who you've become. Not your P and L. Not your Sharpe. Your character."),
    (10, 'S1', 'BTQuant. Speed of Thought.'),
    (11, 'S2', 'Amen.'),
]

for idx, speaker, text in remaining:
    spk = spk1 if speaker == 'S1' else spk2
    fn = f'{OUT}/qwen_line_{idx:02d}_{speaker}.wav'
    if os.path.exists(fn) and os.path.getsize(fn) > 10000:
        print(f'  SKIP {idx}', flush=True)
        continue
    print(f'  gen {idx} ({speaker})...', end=' ', flush=True)
    wavs, sr = model.generate_custom_voice(text=text, speaker=spk, language='English', non_streaming_mode=True)
    audio = np.concatenate(wavs) if isinstance(wavs, list) else wavs
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(fn, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())
    sz = len(audio_int16.tobytes())
    print(f'{sz//1024}KB ({sz/(sr*2):.1f}s)', flush=True)
print('Remaining done', flush=True)
```

## Stitching Command

```python
import numpy as np, wave, os

OUT = '/home/alca/comic/mazemaker-inception-os/v3/voice_btquant_podcast'
sr = 24000
silence = np.zeros(sr // 2, dtype=np.float32)
all_audio = []

for i in range(12):
    fn = f'{OUT}/qwen_line_{i:02d}_S{i%2+1}.wav'
    if not os.path.exists(fn):
        continue
    with wave.open(fn, 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767
        dur = len(frames) / (wf.getframerate() * 2)
        all_audio.append(audio)
        all_audio.append(silence)
        print(f'  line {i:02d}: {len(frames)//1024}KB ({dur:.1f}s)', flush=True)

stitched = np.concatenate(all_audio)
int16 = (stitched * 32767).astype(np.int16)
fp = f'{OUT}/qwen_podcast_full.wav'
with wave.open(fp, 'wb') as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes(int16.tobytes())
print(f'\nPodcast: {len(int16.tobytes())//1024}KB ({len(stitched)/sr:.1f}s) -> {fp}')
```

## Output

- `qwen_podcast_full.wav` — 5041KB, 107.6s
- 12 lines, alternating S1/S2 speakers
- Silaence: 0.5s between lines (SR // 2 samples)