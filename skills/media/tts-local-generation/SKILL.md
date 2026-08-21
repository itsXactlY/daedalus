---
name: tts-local-generation
description: "Generate voiceovers and multi-speaker podcasts using local TTS models (Orpheus 3B, Qwen3-TTS) on a consumer GPU. Pipelines, device placement, CUDA isolation, per-generation timeout."
category: media
---

# TTS Local Generation

Generate high-quality voiceovers and multi-speaker podcasts using local TTS models on a consumer GPU (RTX 4060 Ti 16GB).

## ⚠️ Model Selection — Orpheus 3B DEPRECATED

**Do NOT use Orpheus 3B.** The user explicitly rejected it. All generation uses Qwen3-TTS.

| Model | Size | VRAM | Voices | Status |
|-------|------|------|--------|--------|
| **Qwen3-TTS** | 1.7B | ~3GB | aiden(m), dylan(m), eric(m), ono_anna(f) | ✅ PREFERRED — multi-speaker dialog |

## CRITICAL: Device Placement

**Qwen3TTSModel.from_pretrained() does NOT auto-place on GPU.** Always pass `device_map="cuda:0"`:

```python
model = Qwen3TTSModel.from_pretrained(MODEL, attn_implementation="sdpa", device_map="cuda:0")
```

Without this, the model runs on CPU at ~1 char/s instead of GPU at ~10 char/s.

## CUDA Multiprocessing Isolation

### The Problem
vLLM's V1 engine (v0.22.1) fails with "Engine core initialization failed" when CUDA is already initialized. This happens when running via Hermes background processes or after any torch/CUDA operation in the same process.

### The Fix
1. Use `vllm.LLM` (synchronous) — not async engines
2. Run in a completely fresh Python subprocess
3. Set `VLLM_WORKER_MULTIPROC_METHOD=spawn`
4. Wrap main code in `if __name__ == '__main__':`

### Running from Terminal
For a clean CUDA context, run scripts directly:
```bash
cd /project/dir && python3 script.py
```
NOT via Hermes `background=true` (inherits Hermes' CUDA context).

**Installation path:** `/home/alca/comfy/ComfyUI/custom_nodes/ComfyUI-Qwen-TTS` — use this exact path for `sys.path.insert(0)` calls on this system.

## Orpheus 3B Pipeline

```python
import torch
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from orpheus_tts.decoder import tokens_decoder_sync

# Load synchronous vLLM
tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
llm = LLM(model=model_path, dtype=torch.bfloat16,
          gpu_memory_utilization=0.88, enforce_eager=True, max_model_len=4096)

# Format prompt with Orpheus special tokens
def fmt_prompt(prompt, voice="tara"):
    adapted = f"{voice}: {prompt}"
    pt = tok(adapted, return_tensors="pt")
    ids = torch.cat([
        torch.tensor([[128259]], dtype=torch.int64),
        pt.input_ids,
        torch.tensor([[128009, 128260, 128261, 128257]], dtype=torch.int64),
    ], dim=1)
    return tok.decode(ids[0])

# Generate
ps = fmt_prompt(text, voice="tara")
o = llm.generate([ps], sp)
tids = o[0].outputs[0].token_ids

# Feed tokens to Orpheus SNAC decoder
def gen(tids):
    for tid in tids:
        yield tok.decode([tid])

with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(24000)
    for chunk in tokens_decoder_sync(gen(tids)):
        wf.writeframes(chunk)
```

### Orpheus Tuning Pitfalls

**Do NOT set `stop_token_ids=[49158]`** — this token ID fires prematurely on longer utterances, cutting speech at 2048 tokens even when the text continues. Remove it entirely; let Orpheus finish naturally.

**`repetition_penalty` tuning**: The default 1.3 works for short prompts but causes early termination on longer texts (>150 chars). For narration-length segments, use `repetition_penalty=1.0`. If speech sounds monotonous at 1.0, try 1.05-1.1.

**`ignore_eos=True` generates garbage** — the model produces incoherent filler audio past the natural endpoint. Never set this.

**`max_model_len`** must be ≥ 4096 for any segment over ~250 characters. Default 512 in some vLLM configs will silently truncate the audio at the first few seconds.

**`max_tokens`** should be 6000-8192 for full-page narration. 4000 causes cuts at ~30s of audio.

**Text length**: Keep individual segments under 250 characters for reliable generation without timeouts. Split long monologues at sentence boundaries.

**Voice quality reproducibility**: The canopylabs/orpheus-3b-0.1-ft model may respond differently to the same params as earlier Orpheus checkpoints. Always test-validate with a 50-char sample before batch generation.

## One-Page-Per-Subprocess Pattern (Qwen3-TTS)

Each generation in its own subprocess — clean CUDA context every time:

```bash
python3 -c "
import sys, numpy as np, wave
sys.path.insert(0, '/home/alca/comfy/ComfyUI/custom_nodes/ComfyUI-Qwen-TTS')
from qwen_tts import Qwen3TTSModel
m = Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', attn_implementation='sdpa', device_map='cuda:0')
spk = m.get_supported_speakers()[0]
wavs, sr = m.generate_custom_voice(text=TEXT, speaker=spk, language='English', non_streaming_mode=True, temperature=0.7, top_p=0.9, max_new_tokens=4096)
a = np.concatenate(wavs) if isinstance(wavs, list) else wavs
i16 = (a * 32767).astype(np.int16)
with wave.open('page_XX.wav', 'wb') as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes(i16.tobytes())
"
```

**Performance:** ~25s model load (cached) + ~30s generation = ~55s per page.
**Critical:** Adding `device_map='cuda:0'` is mandatory for GPU acceleration.

### Super-Human Generator (Mazemaker V3)
The project-specific script at `~/comic/mazemaker-inception-os/v3/gen_qwen_superhuman.py` demonstrates the subprocess-per-page pattern in practice using the exact generation command from session `20260608_155345_5d6bba`. See `references/btquant-qwen-podcast-generation.md` for the verbatim commands.
- Loads 15 page scripts from `orpheus_scripts_v6/page_XX.txt`
- Spawns one Python subprocess per page with `subprocess.run()`
- Each subprocess: loads Qwen model, generates, saves WAV, exits
- Output: `voiceover_qwen/page_XX.wav`

This is the reference implementation for any multi-page voiceover project.

## VRAM Coexistence with NMM/Wonderland

The RTX 4060 Ti 16GB runs NMM (Neural Memory Module, ~2.4GiB) and Wonderland API (~1.7GiB) continuously. Do NOT kill these processes. TTS models must fit alongside:

| Model | Weights | Total with KV | Fits with NMM? |
|-------|---------|--------------|----------------|
| Qwen3-TTS 1.7B | ~2.5GB | ~3.5GB | ✅ Yes (~11GB free) |
| Orpheus 3B | ~6.2GB | ~9GB | ⚠️ Tight (needs gpu_memory_utilization=0.6) |

**Rule: Do NOT reduce NMM's VRAM allocation. Do NOT kill NMM processes.**
TTS must work with what's left.

## Qwen3-TTS Pipeline (PREFERRED)

```python
import sys, signal, time, numpy as np, wave
sys.path.insert(0, '/path/to/ComfyUI-Qwen-TTS')
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
    attn_implementation="sdpa",
    device_map="cuda:0"  # CRITICAL
)

# Per-generation timeout (model can hang without flash-attn)
class TimeoutErr(Exception): pass
def handler(signum, frame): raise TimeoutErr()
signal.signal(signal.SIGALRM, handler)
signal.alarm(300)

wavs, sr = model.generate_custom_voice(
    text=text, speaker=spk, language="English",
    non_streaming_mode=True, temperature=0.7, top_p=0.9, max_new_tokens=4096)
signal.alarm(0)

audio = np.concatenate(wavs)
int16 = (audio * 32767).astype(np.int16)
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes(int16.tobytes())
```

## Pitfall: Flash-Attn Warning Pollutes stdout When Using subprocess.run(capture_output=True)

Qwen3-TTS prints a multi-line flash-attn warning to **stdout** (not stderr) on every import:

```text
********
Warning: flash-attn is not installed. Will only run the manual PyTorch version. Please install flash-attn for faster inference.
********
```

When calling `generate_voiceover.py` via `subprocess.run(capture_output=True, text=True)`, the result JSON is buried after this warning. `json.loads(result.stdout.strip())` fails because the first content in stdout is not JSON.

**Fix:** Scan backwards through stdout lines for the last valid JSON object:

```python
lines = result.stdout.strip().split('\n')
for line in reversed(lines):
    line = line.strip()
    if line.startswith('{') and line.endswith('}'):
        info = json.loads(line)
        break
else:
    raise ValueError(f"No JSON found in output: {result.stdout[:200]}")
```

This applies any time you `capture_output=True` on a subprocess that runs Qwen3-TTS. The model's import-side print() calls are unavoidable — they happen before any user code runs — so always use the reverse-scan pattern.

## Flash-Attention Limitation

Without flash-attn (failed to build due to CUDA 13.2 vs PyTorch 12.8 mismatch), Qwen3-TTS falls back to SDPA which is ~5x slower for long texts. SageAttention IS available (auto-detected by SeedVR2) but Qwen3-TTS doesn't support it.

## Voice Pairings for Dialog

| Role | Male | Female |
|------|------|--------|
| Architect/questioner | aiden (speakers[0]) | — |
| System/explainer | dylan (speakers[1]) | ono_anna (speakers[3]) |
| Third | eric (speakers[2]) | — |

**Speaker Index Reference (Qwen3-TTS):**
```python
spks = model.get_supported_speakers()
spk_architect = spks[0]  # 'aiden' — male, skeptical/confused tone
spk_system    = spks[1]  # 'dylan' — male, narrative/explainer tone  
spk_third     = spks[2]  # 'eric' — male, alternate
spk_female    = spks[3]  # 'ono_anna' — female, wise/authority tone
```

## Partial Regeneration Pattern

When some lines already exist and others need regeneration, use the inline pattern:

```python
# Regenerate only missing lines
remaining = [
    (7, 'S2', "The best strategy isn't the highest Sharpe..."),
    (8, 'S1', 'The market never sleeps...'),
    (9, 'S2', "All you have is who you've become..."),
    (10, 'S1', 'BTQuant. Speed of Thought.'),
    (11, 'S2', 'Amen.'),
]

for idx, speaker, text in remaining:
    spk = spk1 if speaker == 'S1' else spk2
    fn = f'{OUT}/line_{idx:02d}_{speaker}.wav'
    if os.path.exists(fn) and os.path.getsize(fn) > 10000:
        print(f'  SKIP {idx}', flush=True)
        continue
    print(f'  gen {idx} ({speaker})...', end=' ', flush=True)
    wavs, sr = model.generate_custom_voice(
        text=text, speaker=spk, language='English',
        non_streaming_mode=True, temperature=0.7, top_p=0.9, max_new_tokens=4096)
    audio = np.concatenate(wavs)
    int16 = (audio * 32767).astype(np.int16)
    with wave.open(fn, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(int16.tobytes())
```

## Stitching Silence Formula

```python
SR = 24000
silence = np.zeros(SR // 2, dtype=np.float32)  # 0.5s silence between lines
```

Total concatenated audio length = audio + silence + audio + silence + ...
Final duration includes all silence padding.

## Workarounds for Long Generations

- Split long monologue lines (>250 chars) at sentence boundaries
- Increase `max_new_tokens` to 8192 for longer texts
- Use `SIGALRM` timeout (300-600s) to prevent infinite hangs
- Each subprocess loads the model fresh (~20s) — batch inside one process when possible

## Gateway Restart Pattern for Async Issues

When gateway async issues appear ("cannot schedule new futures after interpreter shutdown"), restart via:

```bash
hermes gateway stop && sleep 3 && hermes gateway start
```

This sequence stops the gateway service, waits for cleanup, and restarts it. The `sleep 3` allows systemd to fully release resources before restart.