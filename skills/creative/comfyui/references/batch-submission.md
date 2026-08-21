# Batch Job Submission & Monitoring

When you need to generate many images from different prompts (e.g., a trailer's
shot list), you can submit them all to the ComfyUI queue at once. The server
processes them sequentially (1 concurrent job on local, configurable on Cloud).

## Batch Submission via Direct REST API

`run_workflow.py` handles one job at a time. For batches, submit directly to
`POST /prompt`:

```python
import urllib.request, json, random

COMFY = 'http://127.0.0.1:8188'

# Load base workflow JSON (clean — no _meta, no _comment fields)
with open('workflow.json') as f:
    BASE = json.load(f)

PROMPTS = [
    {"prefix": "scene_01", "text": "a dark void with drifting particles"},
    {"prefix": "scene_02", "text": "terminal corruption in deep space"},
    # ...
]

for i, shot in enumerate(PROMPTS):
    wf = json.loads(json.dumps(BASE))  # deep copy
    
    # Inject per-shot parameters
    wf['6']['inputs']['text'] = shot['text']
    wf['25']['inputs']['noise_seed'] = random.randint(1, 9999999999999999999)
    wf['9']['inputs']['filename_prefix'] = shot['prefix']  ← ORGANISES OUTPUTS
    
    payload = json.dumps({'prompt': wf, 'client_id': f'batch_{i}'})
    req = urllib.request.Request(
        f'{COMFY}/prompt',
        data=payload.encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        print(f"  [{i+1}/{len(PROMPTS)}] {shot['prefix']} → {result['prompt_id']}")
    except urllib.error.HTTPError as e:
        print(f"  [{i+1}/{len(PROMPTS)}] FAILED: {e.read().decode()[:200]}")
```

### Key details

- **Deep copy** the base workflow for each submission — don't mutate in-place
- **Set `filename_prefix`** per shot in the `SaveImage` node (`wf['9']` for
  standard workflows) so outputs are organised by act/scene
- **`client_id`** is cosmetic — ComfyUI ignores it for queuing but helps
  identify jobs in `GET /queue`
- **Local concurrent limit is 1** — the remaining jobs queue automatically
- **No rate limit** — you can submit all 20-30 jobs instantly; they queue up

## Monitoring Progress

Three approaches, from simplest to most detailed:

### 1. Check output directory (simplest)

```bash
watch -n 10 'ls ~/comfy/ComfyUI/output/ | wc -l'
```

### 2. Poll individual history entries

```python
import urllib.request, json, time

prompt_ids = [...]  # list of prompt_ids from submission

completed = set()
while len(completed) < len(prompt_ids):
    for pid in prompt_ids:
        if pid in completed:
            continue
        try:
            resp = urllib.request.urlopen(f'http://127.0.0.1:8188/history/{pid}')
            history = json.loads(resp.read())
            if pid in history and history[pid].get('status', {}).get('completed'):
                completed.add(pid)
                print(f"  ✓ {pid[:8]} done — {len(completed)}/{len(prompt_ids)}")
        except:
            pass
    time.sleep(10)
```

### 3. Check queue state (quick overview)

```bash
curl -s http://127.0.0.1:8188/queue | python3 -m json.tool
# → queue_running: [[number, prompt_id, ...]]  # currently processing
# → queue_pending: [[number, prompt_id, ...]]   # waiting
```

## Filename Organisation Pattern

When generating a sequence of shots for a narrative (trailer, storyboard, etc.),
use a structured prefix in the `SaveImage` node:

```python
wf['9']['inputs']['filename_prefix'] = f"act{act_num:01d}_shot{shot_num:01d}"
```

This produces files like:
```
output/
  act0_shot1_00001_.png
  act0_shot2_00001_.png
  act1_shot1_00001_.png
  ...
```

Sorted alphabetically, these group naturally by act for the editing step.

## Estimating Total Time

Per-image time depends on resolution, steps, and VRAM. Measure once:

```bash
# Submit a single test job, note start time, check history
start=$EPOCHREALTIME
# ... submit job ...
# ... wait for completion ...
end=$EPOCHREALTIME
echo "Per-image: $(bc <<< \"$end - $start\") seconds"
```

Then multiply by job count: `N × per_image_time ÷ concurrent_jobs`.

**Typical on RTX 4060 Ti (16 GB):**
| Resolution | Steps | Time | Jobs/hr |
|------------|-------|------|---------|
| 1024×1024  | 30    | ~85s | ~42     |
| 1216×688   | 30    | ~95s | ~38     |
| 1216×832   | 30    | ~95s | ~38     |

## Cleaning Up Between Batches

Output files accumulate. If you need a clean slate:

```bash
rm ~/comfy/ComfyUI/output/trailer_act*.png
```

The ComfyUI `history` API does not auto-clear — old prompt_ids remain
queryable indefinitely.

## Pitfalls

1. **Deep copy or reload the workflow JSON per job** — mutating the same dict
   and submitting 24 references to the same mutable object will submit the last
   mutation 24 times.
2. **Filename prefix numbering resets** — ComfyUI appends `_{sequence:05d}` to
   `filename_prefix` per server session. If you restart the server between
   batches, sequence resets to `00001`.
3. **Stdout from background process may be empty** — ComfyUI's progress bars
   go to stderr, not stdout. `GET /history/{id}` is the reliable completion
   check, not output parsing.
4. **First job after server start is ~2× slower** — model weights load from
   disk into VRAM. Subsequent jobs reuse the loaded model. The batch monitor
   should not panic if the first file takes 120s+ while the rest take 60s.
