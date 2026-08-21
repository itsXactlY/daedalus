# Git-Timeline Auditing + Thesis-Driven Inception Waves

Two deep-audit techniques proven in the 2026-08-07 mazemaker second-round audit
(5 orchestrators + basis crew, both repos, ~90 findings, every defect traced to
its introducing commit).

## 1. Git-Timeline Auditing ("ab wann war was kaputt")

The operator asks not only WHAT is broken but WHEN the engine started to
degrade silently. For every defect, find its INTRODUCING COMMIT:

```bash
git log -S'<symbol>' -- <file>      # commit that introduced/changed a symbol
git blame -L <start>,<end> <file>   # exact line introduction
git log --follow --oneline -- <file> # file history across renames
```

Then build a timeline table: `date | commit | what broke/degraded silently`.
Findings from the mazemaker audit that only became actionable through the
timeline:

- The 12.3 GB GPU-arm path (get_all() → Python floats) was introduced
  2026-05-18 (`1e0d590`) and fixed only 2026-08-07 — 81 days latent, causing
  7 kernel OOM kills in one morning.
- `EMBED_BACKEND=http` was a dead value for 74 days (`66157d6` 05-20, fixed
  `d8fa3d6` 08-07) — every process silently loaded a second BGE model.
- Synthesis was broken FROM BIRTH (`41ad53a` 05-17): 3600s anchor window vs a
  pre-existing 300s TTL, plus a never-installed `smollm3` default. The phase
  NEVER succeeded (0 proposals in 4/4 runs; zero success lines in all logs).
- A `_cc_get` NameError in the NREM phase existed since the compute.toml
  policy move (`02fda91`) — the phase crashed 4s into every cycle and the
  cycle ran on without it, silently.
- NREM/REM/Insight tests: last documented green suite 2026-04-21; the suites
  rotted silently for months (one demanded a file excised 05-01).

Cross-repo divergence check: the same file in two repos (pro/free fork) with
asymmetric cherry-picks — fixes land in one line, not the other. Free repo had
NO iter_for_gpu_arm/dead-man switch; its CI never ran (default branch
`main-v2` not in triggers `[master, main]`).

Pitfall: commit IDs in worker reports are not trustworthy — verify with
`git cat-file -t <sha>` before citing (one worker cited a fix commit that
existed in no repo).

## 2. Thesis-Driven Inception Waves

For maximal depth: dispatch orchestrator agents, each carrying ONE sharp,
falsifiable thesis ("the bottleneck is X because Y"), with permission to spawn
up to N leaf children that each verify a single sub-claim with code/git/log
evidence. Verdicts are BESTAETIGT / WIDERLEGT / TEILWEISE — a refuted thesis
is a result.

Example theses from the mazemaker round (all five verified in ~10 min wall):

| Thesis | Verdict |
|--------|---------|
| A: get_all() float-materialisation is THE bottleneck; no chunked path exists | BESTAETIGT (SQLite had zero chunking; fetchmany=0 in repo) |
| B: >=5 silent degradation modes without warn/error logs | BESTAETIGT (7 modes; "GPU recall ARMED ... on cpu" INFO reads as healthy) |
| C: dream cycle is a chain of silent no-ops, consolidation effectively dead | BESTAETIGT (via basis stream after orchestrator timeout) |
| D: build/deploy chain cannot produce reproducible images | TEILWEISE (mechanisms real; fresh build was reproducible 7/10) |
| E: worker RAM steady-state = loaded state, not a leak; oomd kills due to host oversubscription | BESTAETIGT |

Rules:
- Give each child ONE sub-question, full context, and the requirement to
  answer with evidence (file:line, commit hash) or explicitly say "cannot
  verify" — no padding.
- Orchestrator timeout is a real failure mode on free/weak models: tail the
  live transcript first, then re-dispatch THAT stream with a hard
  "FINAL ANSWER MUST BE THE COMPLETE REPORT" requirement. If it times out
  again, cover the stream yourself or on a stronger model.
- Consolidate verdicts into one table with the proof chain per thesis; the
  refuted theses are as valuable as the confirmed ones (they save future
  sessions from re-investigating).
