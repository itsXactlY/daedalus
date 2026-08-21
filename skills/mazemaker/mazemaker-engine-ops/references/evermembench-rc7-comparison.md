# EverMemBench 1:1 vs RC7 — harness facts (session 2026-08-08)

Reconstructed RC7 bench setup from mazemaker memory + the committed
pipeline scripts (`~/projects/mazemaker/benchmarks/external/`):

- Korpus: EverMemBench-004, 10.388 mems / 72.943 edges in an isolated PG DB
  (`evermembench` — NEVER the live `mazemaker` DB; verify 0 bench labels
  in the live DB after ingest).
- Engine: `retrieval_mode=advanced`, `use_hnsw=auto`, `think_engine=ppr`,
  `rerank=True`, `retrieval_candidates=512`,
  `channel_weights={"colbert": 1.5, "dae": 1.0}`, 4 dream cycles.
- Answerer: qwen2.5:3b via local Ollama; Judge: deepseek-v4-flash.
- RC7 references (documented, NOT reproducible without gpt-4.1):
  46.4 vs EverMemOS 44.6 leaderboard (gpt-4.1-mini/nano protocol),
  k=30: 48.56% pooled, budget answerer (deepseek) 51.1/52.6,
  48.7% comparison-page claim. fact:evermembench-leaderboard-46.4-vs-44.6-2026-07-05.

## Harness shape (rebuilt, eval.cli was lost)

Data: `dialogue_004.json` = {type, generated_at, statistics, dialogues},
dialogues = {date: {Group N: [{speaker, time, dialogue}]}}.
`qa_004.json` = {metadata, qars:[{id, Q, A}]} — 626 questions; categories
are encoded in the id prefix (F_SH_Top004_001 etc.).

Pipeline per question: recall(Q, k) → context → answerer → judge
(MC/OE/Total mean). Both models local: qwen2.5:3b via Ollama
(`http://host.containers.internal:11434` inside containers), judge via
the deepseek API (`https://api.deepseek.com/chat/completions`, model name
IS `deepseek-v4-flash` — the API error message lists it; key from
`~/.hermes/config.yaml` providers.deepseek.api_key, pass as env, never
print).

## Pitfalls found

- **qwen2.5:3b collapses the score**: a full run scored 1.28% (8/626)
  while the top-10/30 recall was thematically perfect. The small answerer
  cannot extract paraphrased gold answers from truncated contexts
  ("not specified in the provided context", or extrapolates 70% where the
  gold is 65%). The RC7 46.4 used gpt-4.1-mini — the answerer, not the
  retrieval, is the variance. For ENGINE comparison use the deterministic
  ANSWER-RECALL@k substring check (gold answer normalized-substring in
  top-k recall) — no LLM, isolates the retrieval changes.
- **deepseek-v4-flash API quirk**: with max_tokens 5-30 it returns EMPTY
  content with finish_reason=length. Needs max_tokens ~60 to emit
  "CORRECT"/"WRONG". Ollama cloud models (`deepseek-v4-flash:cloud`)
  require a subscription — use the direct API with the config key.
- **use_cpp=True segfaults** (EXIT 139) in the mcp container at engine
  init — bench containers use `use_cpp=False`.
- **Corpus ingest via remember()** = one HTTP embed round-trip per memory
  (~220 ms × 10k = 30+ min). Brute-force: bulk INSERT + batch embed.
  Saved as decision:bench-ingest-bruteforce-db-batch (mazemaker id 1156634).

## Local answerer/judge era numbers (run_pipeline.sh)

Stages FLOOR → DREAM → COMPLETE; answerer qwen2.5:3b via ollama, judge
deepseek-v4-flash via NIM; `eval.cli --dataset dataset/004/dialogue.json
--qa qa_004.json --system mazemaker --top-k 10`. Exact stage accuracies
were not recoverable from memory this session — the documented anchors
are the gpt-4.1 leaderboard numbers above.
