# Env-Knob Gate Failures — 2026-08-08 forensics (5396678 + a512c36)

Two silent gate failures on the real 215k production DB that made the
operator's OFF-knobs inert. Both are the "überschriebene Fixes" class:
the code LOOKS gated, the deployed knob does nothing.

## 1. DAE env-name mismatch (5396678)

Symptom: full cycle = 525.9 s; `dae` phase reported `written=215651`
(full-corpus DAE compute) although the quadlet sets `MAZEMAKER_DAE_ENABLED=0`.

Root cause:
- quadlet: `Environment=MAZEMAKER_DAE_ENABLED=0`
- engine (`_phase_dae`): `os.environ.get("MM_DAE_ENABLED") or "1"` — the LEGACY name.
- The two names never met → gate read empty → "1" → DAE ran.

This also means the earlier verification (hermes-verify-quadlet-envs,
"DAE skipped with env 0") was real but only proved the gate works for
`MM_DAE_ENABLED` — the DEPLOYED name was never connected to the code.

Fix:
```python
_dae_env = (os.environ.get("MAZEMAKER_DAE_ENABLED")
            or os.environ.get("MM_DAE_ENABLED") or "1").strip().lower()
if _dae_env == "0":
    return {"skipped": "mm_dae_enabled_off"}
```

Measured after fix: `dae: SKIPPED mm_dae_enabled_off`; cycle back to the
72.3 s class.

Lesson: after renaming an env knob in the quadlet, grep the ENGINE for the
old name — a same-meaning env renamed on the deploy side while the code
keeps the old name is a silent "knob does nothing". Unit-testing the gate
logic with the WRONG env name proves nothing about the deployed system.

## 2. ColBERT read-path gate (a512c36)

Symptom: `embed_colbert` HTTP calls every ~1 s during the cycle (measured
05:25) although `MM_COLBERT_ENABLED=0`.

Root cause: the knob gated only token WRITES (`_colbert_write_enabled`,
memory_client.py ~1569). The READ channel weight came from two OTHER
sources neither the env touched:
- retrieval-mode presets (memory_client.py ~1536-1542): advanced/hybrid → 0.5, skynet → 1.2
- compute.toml overlay `[recall_advanced] colbert_weight = 1.5` (rendered)

So `channel_weights["colbert"]` stayed > 0 → recall fired embed_colbert
calls every cycle.

Fix: env wins LAST, after every preset/overlay:
```python
if not (os.environ.get("MM_COLBERT_ENABLED", "0").strip().lower()
        in ("1", "true", "yes", "on")):
    self._channel_weights["colbert"] = 0.0
```
Side effect (intended): with NO env the channel is now OFF by default
(was: mode preset 0.5); only explicit MM_COLBERT_ENABLED=1 activates it.

Verified matrix:
| env | retrieval_mode | channel_weights arg | result |
|-----|---------------|---------------------|--------|
| 0   | advanced      | -                   | 0.0    |
| 0   | skynet        | -                   | 0.0    |
| 0   | advanced      | {colbert: 1.5}      | 0.0    |
| 1   | advanced      | -                   | 0.5    |
| none| advanced      | -                   | 0.0 (new default) |

Lesson: one feature with two switches (write path + read path) driven by
different config sources is a guaranteed "off doesn't stay off" bug. The
operator env must be the final authority on BOTH paths — put the env gate
LAST in the constructor, after presets and overlays.

## The pod-GPU run recipe (the "einmal richtig" audit)

Host CPU runs are noise (no torch → GPU recall skipped + CPU fallback +
minutes-long cycles). Real numbers require:

```bash
POD=$(podman inspect systemd-mazemaker-pgvector --format '{{.Pod}}')
podman run --rm --pod "$POD" --user 0 --device nvidia.com/gpu=all \
  --secret mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD \
  -v /tmp/audit.py:/audit.py:ro \
  -v /home/alca/projects/mazemaker-pro/python:/app/core:ro \
  -v ~/.mazemaker/license.jwt:/root/.mazemaker/license.jwt:ro \
  -v ~/.mazemaker/jwt.v1.pub.ed25519:/secrets/jwt.v1.pub.ed25519:ro \
  -v ~/.mazemaker/compute.toml:/root/.mazemaker/compute.toml:ro \
  -e MAZEMAKER_LICENSE_PATH=/root/.mazemaker/license.jwt \
  -e MAZEMAKER_PUBKEY_PATH=/secrets/jwt.v1.pub.ed25519 \
  -e MM_COLBERT_ENABLED=0 -e MAZEMAKER_DAE_ENABLED=0 -e EMBED_BACKEND=http \
  -e EMBED_CLIENT_ONLY=1 -e MM_RECALL_GPU_STRICT=1 \
  -e MM_EMBEDDING_WORKER_URL=http://localhost:8766 -e PYTHONPATH=/app/core \
  localhost/mazemaker-v2-mcp:gpu python3 /audit.py
```

The script must assert the quadlet envs at the top (a missing env = "not
the real path"), must NOT write test memories into the production DB
(bench-müll), and reports: torch.CUDA, GPU-recall armed, channel weights,
phase skips, per-phase counts, cycle duration.

Measured: torch-CUDA True (RTX 4060 Ti), GPU recall armed, colbert weight
0.0, full cycle 72.3 s on the real 215,561-memory DB.
