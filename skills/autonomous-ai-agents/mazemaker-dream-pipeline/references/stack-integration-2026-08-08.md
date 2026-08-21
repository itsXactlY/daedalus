# Full-Stack Integration Audit — 2026-08-08

The production-shape test level: a REAL `DreamEngine.run_cycle()` over ALL
phases, against BOTH backends, plus the recall chain, policy gates and the
worker CLI. This level found two real bugs the unit/function tests could not
(#16 get_all(False) crash, #17 stage_s default ON).

## Structure that worked

- Host part (`audit-integration-stack.py`, runs on the dev box, no pod):
  - A. SQLite full cycle: 120 memories (hash backend) + `DreamEngine.sqlite(...).run_cycle()` — assert every phase key present (`nrem, supersedes, rem, insights, dae, afe, synthesis`), DAE+Synthesis `skipped`, NREM ran (`skipped is None`, processed >= 0). Env `MM_DAE_ENABLED=0` is the production policy — set it BEFORE engine init or the DAE phase attempts its (broken-on-SQLite) upsert and logs "DAE compute crashed: near SET".
  - B. Recall chain: recall / think / graph / stats / recall_multi / recall_multihop on a 50-memory tmp DB.
  - C. Policy gates: `compute_config.flag("dream", "stage_s_enabled") is False`.
  - D. Worker CLI: `python dream_worker.py --db <tmp> --embedding-backend hash --phase nrem --once` (flags from `--help` — there is NO `--no-cpp`).
- Pod part (`audit-integration-pg.py`, runs in a throwaway container on the pgvector pod): Mazemaker with `MM_DB_BACKEND=postgres` against `mazemaker_test` + `DreamEngine.postgres(dsn, neural_memory=nm).run_cycle()` + PG recall/stats.

## Mount traps for the PG integration container (all three required)

```
podman run --rm --pod <pgvector-pod> --user 0 \
  --secret mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD \
  -v <script>:/audit.py:ro \
  -v mazemaker-pro/python:/app/core:ro \
  -v ~/.mazemaker/license.jwt:/root/.mazemaker/license.jwt:ro \
  -v ~/.mazemaker/jwt.v1.pub.ed25519:/secrets/jwt.v1.pub.ed25519:ro \
  -v ~/.mazemaker/compute.toml:/root/.mazemaker/compute.toml:ro \
  -e MAZEMAKER_LICENSE_PATH=/root/.mazemaker/license.jwt \
  -e MAZEMAKER_PUBKEY_PATH=/secrets/jwt.v1.pub.ed25519 \
  -e PYTHONPATH=/app/core localhost/mazemaker-v2-mcp:gpu python3 /audit.py
```

- WITHOUT the license the engine logs `"MM_DB_BACKEND=postgres requested but
  the Postgres backend is a Pro feature; falling back to SQLite"` and the
  "PG cycle" silently runs on SQLite — you verify nothing. This fallback is
  silent by design; grep for it.
- WITHOUT the compute.toml the DEFAULTS decide the phases — and
  `stage_s_enabled` was True there (bug #17), so Stage S ran during the test
  and the "synthesis should be skipped" assertion failed. The failure mode IS
  the finding: a default that contradicts the shipped policy.

## Findings from this level (all fixed fc1d508)

1. `postgres_store.get_all(include_embeddings=False)` — SELECT always took 9
   columns, `_row_to_dict` false-branch unpacked 7 → ValueError on every
   vector-less call. The NREM path uses vector-less get_all, so the crash was
   in the real cycle. Fix: conditional SELECT columns.
2. `compute_config.DEFAULTS["dream"]["stage_s_enabled"] = True` → False.
   Without a rendered toml, Stage S ran against operator policy.

## NREM-batch note (38s-era lever, not yet fixed)

`batch_strengthen_connections` (abstract dream_engine.py:235-243 and PG impl)
is a Python loop calling `strengthen_connection` per edge (~24k individual
updates per cycle). PG's batch_weaken is already a chunked bulk. Bundling the
strengthen side (COPY to temp + ONE UPDATE FROM, like the PG strengthen bulk
path already does) is the open lever for the 38s reclamation.
