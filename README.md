# Daedalus

**An autonomous agent harness built to retrieve its history instead of hauling it.**

Not a chat wrapper. It runs its own loop, maintains its own skills, delegates to
subagents and schedules its own work — on top of **Mazemaker**, a memory engine
where recall is a graph traversal rather than a transcript replay.

Forked from Hermes Agent **0.8.0**. Requires Python 3.14+.
See [CHANGELOG.md](CHANGELOG.md).

---

> ## ⚠️ READ THIS BEFORE YOU INSTALL IT
>
> **This is not a drop-in upstream replacement.**
>
> Daedalus was deliberately taught to stop carrying its own history. That is not
> a setting — it is the change everything else hangs off, and it is where the
> token savings come from. It only works because something else holds what it
> stopped carrying.
>
> **Run it without Mazemaker and you do not get a smaller agent. You get an
> amnesiac one** — engineered to forget, with nothing remembering on its behalf.
> It loses the thread inside a session and everything between them. Worse than
> upstream, by construction.
>
> To run it as intended you need a Mazemaker backend — **Pro+ at
> [mazemaker.online](https://mazemaker.online)**. If you are not going to run
> Mazemaker, run upstream instead. No amount of configuration changes this.

---

## The receipts

**Same model. Same task. Only the harness differs.** Both sides asked for a
WebJS snake game, both delivered one — `Qwen3.6-35B-A3B`, same machine, same
moment.

| | upstream harness | **Daedalus** |
|---|---|---|
| context consumed | **25.7K** / 256K · 10% | **9.4K** / 262K · 4% |
| result | working game | working game |

**63% fewer tokens for the same work** — the other harness spent **2.7×** as
much to arrive at the same place. Daedalus closed it in two API calls: 9,403
prompt, 281 completion.

**And it did that with more available to it, not less.** The cheap side had a
300+ skill catalogue in reach; the expensive side ships fewer than 80. Capability
went up and cost went down together, because a catalogue indexed by name and
pulled on demand does not bill you for every entry on every turn.

**What that budget buys instead:** one session — smalltalk, a few trick
questions, then a **682-line animated WebGL shader page** written from scratch,
**~40,000 tokens total** —
[tests/basement_not_safe/wall-of-shame.html](tests/basement_not_safe/wall-of-shame.html).
The model was `Qwen3.6-35B-A3B` at **IQ3_XXS** — 3B active parameters at ~3.4
bits per weight. The quant tier the internet calls a toy. It is not a toy; it was
being starved.

**Why it compounds.** A 63% saving on a snake game is a number. The same saving
on work that runs for days or weeks is the difference between possible and not.
Long-horizon work is where transcript-hauling agents die: the window fills,
compaction eats the early decisions, and by day three the agent confidently
rebuilds something it already built. An agent that retrieves has no such ceiling.

That is the whole thesis. Everything below is how.

---

## Why fork 0.8.1

Hermes **0.8.0** was the high-water mark, and it was earned. What followed was
not a continuation of that work — it was accumulation. Tool surfaces and skill
catalogues grew, and none of it is free: every skill name sits in the system
prompt on **every turn**, so a catalogue is a tax levied before the model reads
the question.

Meanwhile the things that decide whether an agent is any good went unattended: a
search tool reporting *no matches* for a pattern it failed to compile; an agent
believing it had 128K of context when it had a million; one misconfigured field
burning ~13–16K tokens per retry. None of it crashed. It just made the agent look
stupid and expensive.

**This fork inverts the priority: intelligence per token, and nothing shipped
that is not maintained.** Retrieve instead of haul. Curate instead of grow. Fix
the tools that lie.

> **On the history.** This repository starts at a single commit — deliberate, not
> a lost `.git`. The fork diverged far enough that upstream's ancestry was
> misleading rather than useful. Upstream remains
> [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), MIT, and the
> licence travels with the code.

---

## Mazemaker: the part that matters

Every agent forgets. The usual answer is to drag the transcript along until the
window fills, compress it, and lose the details that mattered.

Mazemaker is a persistent cognition layer, not a scratchpad. Conversations are
written as they happen; before each turn the agent pulls back what is actually
relevant.

```yaml
memory:
  provider: mazemaker
```

| tool | what it does |
|---|---|
| `mazemaker_recall` | find what is relevant to this question |
| `mazemaker_remember` | keep something durable |
| `mazemaker_think` | traverse from one memory to what connects to it |
| `mazemaker_graph` | inspect the structure |

History the agent can retrieve is history it does not have to carry. An agent
re-sending 200K of transcript pays for it on every call; one recalling the three
things that matter pays for three. It survives the session ending — restart
tomorrow and the work is still there, retrievable rather than summarised into
vagueness.

The live instance backing this fork holds **218,700 memories and 704,242
connections**, and answers recall in milliseconds. It is benchmarked in public:

| | |
|---|---|
| LongMemEval R@5 | **0.8426** — 500 questions, 25k-memory haystack |
| R@10 | **0.9000** |
| Hop-2 reasoning R@10 | **0.00 → 1.00** — structurally impossible for flat vector stores |
| Post-consolidation synthesis | **0.00 → 0.43** on facts unreachable from any single memory |
| `gemma3:270m` | **18/20** — 270M parameters, on a Raspberry Pi |

Every artifact is public, negative controls included:
[Inception Benchmarking](https://mazemaker.online/blog/inception-benchmarking/).

A 270M model scoring 18/20 and a 3B-active model writing a shader page in 40k
tokens are one claim seen twice: **most of what looks like model weakness is
harness and memory overhead wearing a model's clothes.**

**Every turn is accounted for.** Usage is reported from what the model actually
read, not the billed subset — the two disagree by ~900 tokens on a single small
call — with real dollar cost alongside. That is the only way "40,000 tokens"
means anything.

**It degrades safely.** If the pod is unreachable, recall and writes fail
silently and the agent runs on its normal window. A missing memory layer is a
quieter agent, not a broken one. Endpoint defaults to `http://127.0.0.1:8765`
(`MM_WONDERLAND_URL` to override).

---

## What else it does

- **Runs anywhere there is an OpenAI-compatible endpoint.** llama.cpp, Ollama,
  vLLM, Unsloth Studio, OpenRouter, Anthropic, or your own. Model choice is a
  config line, not a rewrite.
- **Builds its own skills.** Solves a problem, writes the solution down so the
  next agent starts from the answer. 100 curated skills across 20 packs — every
  name is prompt weight, so the catalogue is curated rather than accumulated.
- **Delegates.** Subagents with isolated context for work that would fill the
  parent's window.
- **Keeps running.** Gateway, cron, background curation, self-healing pipelines.
- **Talks where you are.** Discord, ACP, MCP — as a server or a client.

## What got fixed

Real defects, found by *using* the thing. No claim about which exist in any other
build — they were costing **this** lineage, quietly:

- **Search stopped lying.** `search_files` ran as a shell pipeline, so ripgrep's
  error exit was masked by `head` and an invalid pattern returned *no matches*.
  A search for `legacy_connect(` reported **0 hits where there were 5**. A tool
  returning nothing is indistinguishable from a codebase containing nothing.
- **The agent knows how much context it has.** It reads the real window from the
  endpoint instead of a hardcoded 128,000 — and re-checks it, rather than
  resolving once at startup and never again.
- **Plugins actually ship.** No package data was declared, so the wheel carried
  no `plugin.yaml` for *any* plugin: every one worked from a source checkout and
  was invisible to an installed copy.
- **Two functions that could never have run.** One imported a helper that existed
  nowhere, the other referenced an unimported name. Both dead on first call.

None of these announce themselves. The clearest case: one misconfigured field
produced **73% of all logged errors** across four failed API sequences, each
retrying three times at ~13–16K tokens per failure. Nothing crashed. It just cost
money and looked like the model being slow.

Per-suite against the build this forked from, on identical inputs: `agent`
5/1022, `tools` 103/2830, `cli` 8/351, `run_agent` 1/688 — zero failures unique
to this distribution.

## No shared namespace, no shared secrets

Daedalus and Hermes sit side by side without touching. Own command, own modules,
own `DAEDALUS_*` environment, own home. `HERMES_HOME` is not read — not even as a
fallback — so a fresh install cannot inherit another agent's state or credentials.

It ships without credentials at all: `auth.json`, `config.yaml`, `.env`, keys and
tokens are runtime state, gitignored, with only `.example` templates in the tree.

---

## Install

```bash
./install.sh                       # persistent tool install -> `daedalus`
./install.sh --run                 # one-shot, installs nothing
./install.sh --dev                 # editable .venv
./install.sh --extras "messaging,cron,mcp"

daedalus setup                     # interactive first run
daedalus                           # go
```

Bootstraps [uv](https://astral.sh/uv) if missing.

| Path | Purpose |
|------|---------|
| `~/.daedalus/` | Home: config, state, sessions, skills |
| `.env.example` | API key template — copy to `.env`, never commit |
| `cli-config.yaml.example` | Annotated reference config |

Skills live in `skills/` in this tree, and the default home *is* this directory,
so they work immediately from a source checkout.

**A packaged install gets none of them.** Skills are `SKILL.md` files outside any
Python package, so the wheel carries zero of the 100 — a `pip`/`uvx` install comes
up reporting *No skills installed* while this repo holds all of them. Fix it with:

```bash
daedalus skills sync              # pull skills/ from this repo into DAEDALUS_HOME
daedalus skills sync --dry-run    # show what would change
daedalus skills sync --prune      # also drop skills the repo no longer has
```

`daedalus update` does not cover this. It resolves `PROJECT_ROOT`, which on a
packaged install is `site-packages` and not a git checkout, so its git path is
unavailable and its zip fallback would unpack the whole repository over
`site-packages` — putting skills nowhere the agent looks. `sync` extracts
`skills/**` only, straight into `DAEDALUS_HOME/skills`, and leaves anything else
in that directory alone unless `--prune` is asked for, because hub-installed and
hand-written skills share it.

Note that `pip install --upgrade` from this repo is a no-op while the version
string is unchanged; use `--force-reinstall --no-deps` to move a packaged install
onto current `main`.

## Experimental

**Claude Code as the model backend** — run on a Claude subscription with no API
key, via a shim in front of the Claude Code CLI. Working: auth, per-model context
windows, model switching, isolation. Not working: tool calling is unreliable,
turns intermittently come back empty. **Disabled by default and not recommended
for real work.** See [`scripts/claude_code_shim.py`](scripts/claude_code_shim.py).

## Licence

MIT, upstream Nous Research. See [LICENSE](LICENSE).

---

## The rest of it

Daedalus runs on Android, unrooted — Podroid provides the container, Alpine runs
inside it, and the agent lives there. Not a remote agent with a phone client: the
app talks to it on loopback, prefers it whenever it answers, and falls back to a
paired desktop only when it does not. The model provider can still come from the
machine you paired with. The *agent* is what lives in your pocket.

**We don't just pinky-promise that YOUR data stays YOURS — there is nowhere else
for it to be.** No central server, no account, no copy on our side to leak, sell
or hand over. That is a design position, not a policy page, and we wrote it down
before we built on it: **[On Local-First Data
Sovereignty](https://mazemaker.online/manifesto/)** — April 2026, unchanged since.

None of this started here. **remainder.online** was engineered first;
**mazemaker.online** and **mazemaker.dev** were researched and built after it.
Then rinse and repeat, for all the rest. Every piece is scar tissue — north of a
**trillion tokens** spent finding out what breaks, turned into what it became.
What survived is what stopped breaking.

**Iris** — the god of messages — grew up beside it rather than after it. Still in
private testing; ships in **The Box**. That is all we will say about it here.

The labyrinth got built. The minotaur got banned. That imploded the entire matrix
— which is how we found the next door.

More infos soon:tm:
