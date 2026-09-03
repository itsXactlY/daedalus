# Daedalus

**A 27-billion-parameter model, a 131,000-token memory, and two AI servers —
all on one gaming graphics card that costs about as much as a phone.**

That sentence is supposed to be impossible. Here is the machine it runs on:

```
NVIDIA RTX 4060 Ti · 16 GB · a mid-range consumer card

main model        13,822 MB   Qwen3.8-27B dense, 131,072-token context
helper model         200 MB   Qwen3-1.7B, runs on the CPU
memory engine        300 MB   222,409 memories, 1.5M connections
                  ─────────
free                 924 MB   yes, that is under one gigabyte to spare
```

About 27 tokens a second on average, peaking near 40. Not a datacenter. Not
an H100. A card people buy to play games on.

---

## Why that is a big deal

Skip this if you already know. Here is the short version for everyone else.

An AI model needs two things in memory. **The model itself** — the weights,
the actual brain, about 10 GB here. And **the conversation** — everything it
has been told so far, which it has to keep looking at while it answers.

That second part is the problem nobody warns you about. It is called the KV
cache, and it grows with every word. For this model it costs **73 kilobytes
per token**. A full 131,000-token conversation therefore needs **9.1 GB** of
memory — on top of the 10 GB the brain already takes.

10 plus 9 is 19. The card holds 16. So it does not fit, and normally you stop
here: shrink the conversation to a quarter of its size, or buy a card that
costs five figures.

**The trick is that the conversation does not have to live on the graphics
card.** It sits in ordinary system RAM, and the card keeps only the part it is
reading right now — like working from a desk with one page in front of you and
the rest of the folder within arm's reach. That is
[adaptive KV streaming](https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming),
and it is doing the heavy lifting behind the number at the top of this page.

Full attention over the whole conversation. Nothing summarised away, nothing
approximated.

---

## The part that is actually ours

The hardware trick gets the model in the door. It does not make the model
*good*. That is the other half, and it is the half this project is about.

Here is the thing nobody tells you: **most of what looks like a stupid AI is a
smart AI drowning in junk.**

Every turn, a typical agent hands its model a pile of things it did not ask
for. The full list of every tool it owns. The name and description of every
skill installed. The entire conversation so far, replayed from the top. Then,
somewhere at the very bottom, your actual question.

The model reads all of it. Every time. You pay for all of it. Every time.

We measured what that costs on a real session:

| what it was | before | after |
|---|---|---|
| listing the skill catalogue | **24,470 tokens** | **329** |
| one working session's context | **70,397 tokens** | **8,967** |

The skill catalogue alone was eating 78% of an entire session. Not because
anyone used those skills. Just because they were *listed*.

**Daedalus stops handing the model things it did not ask for.**

- **Tools arrive on request.** 18 are in the window; 91 exist. The rest are one
  question away.
- **The catalogue is searched, not recited.** Ask for what you need and you get
  matches. All 350 skills are still reachable. None of them cost anything until
  they do.
- **Bulky results leave the window and stay reachable.** When a file the agent
  read ten minutes ago ages out, it is written to a scratch file and replaced
  by one line saying what it was and where it went. The agent reads it back if
  it needs it. Nothing is lost. It just is not being carried anymore.
- **The conversation itself lives in a memory engine.** More on that below,
  because it is not optional.

Give a model room to think and it thinks. Two different ones make that point
here, and they are worth keeping apart.

**The one running now is `Qwen3.8-27B` — dense, not a mixture-of-experts.** All
27 billion parameters work on every token; there is no sparse routing doing the
heavy lifting. It is squeezed to roughly three bits per weight by
[ISTA-DASLab's GSQ-RCO](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF),
a quantisation method that lands **near-lossless against full FP16**. That is
the whole reason a 27B dense model fits beside a 131k context on one consumer
card at all: three bits that still answer like sixteen.

**A different model wrote the shader page.** `Qwen3.6-35B-A3B` — a
mixture-of-experts with only 3 billion parameters active per token, at
`IQ3_XXS`. The tier the internet writes off as a toy. After some smalltalk and
a few trick questions it produced a 682-line animated WebGL page from scratch,
in about 40,000 tokens total. It is not a toy. It was being starved.

---

## ⚠️ It needs a memory engine. This is not a suggestion.

Daedalus was deliberately taught to **stop carrying its own history**. That is
where the savings come from. It only works because something else is holding
what it stopped carrying.

That something is **[Mazemaker](https://mazemaker.online)**. Every turn is
written there as it happens. Before answering, the agent pulls back the few
things that actually matter instead of re-reading everything.

**Run Daedalus without it and you do not get a leaner agent. You get an
amnesiac one** — engineered to forget, with nothing remembering on its behalf.
It loses the thread inside a session and everything between them. Worse than a
normal agent, by design.

If you are not going to run Mazemaker, run something else. No configuration
fixes this.

The instance behind these numbers holds **222,409 memories and 1,500,622
connections** and answers in milliseconds. It is benchmarked in public,
negative controls included:

| | |
|---|---|
| LongMemEval R@5 | **0.8426** — 500 questions, 25k-memory haystack |
| R@10 | **0.9000** |
| Two-hop reasoning R@10 | **0.00 → 1.00** — impossible for flat vector search |
| `gemma3:270m` | **18/20** — a 270-million-parameter model, on a Raspberry Pi |

[Inception Benchmarking](https://mazemaker.online/blog/inception-benchmarking/)
has the full write-up.

A 270M model scoring 18/20 and a 3B model writing shader pages are the same
claim twice: **most apparent model weakness is overhead wearing the model's
clothes.**

If the engine is unreachable, recall goes quiet and the agent falls back to its
normal window. A missing memory layer makes it forgetful, not broken.

---

## The receipts

Same model, same task, same machine, same afternoon —
`Qwen3.6-35B-A3B` on both sides. Both harnesses were asked for a browser snake
game. Both delivered one.

| | a conventional harness | **Daedalus** |
|---|---|---|
| context used | 25.7K / 256K | **9.4K / 262K** |
| result | working game | working game |

**63% fewer tokens for the same result.** The other one spent 2.7× as much to
end up in the same place. Daedalus closed it in two calls.

And it did that with *more* available to it. The cheap side had 350 skills
within reach; the expensive side ships fewer than 80. Capability went up while
cost went down, because a catalogue you search does not bill you for entries
you never open.

**Why this compounds.** Saving 63% on a snake game is a statistic. Saving it on
work that runs for a week is the difference between finishing and not.
Long-running work is where transcript-hauling agents die: the window fills, the
summariser eats the early decisions, and by day three the agent confidently
rebuilds something it already built. An agent that retrieves has no such
ceiling.

---

## What else is in it

- **Runs on anything OpenAI-shaped.** llama.cpp, Ollama, vLLM, OpenRouter,
  Anthropic, your own endpoint. Switching is a config line.
- **Writes its own skills.** Solves something once, writes it down, starts from
  the answer next time. 100 curated skills across 24 packs in this repo — every
  name would be prompt weight if the catalogue were recited, so it is curated
  rather than hoarded.
- **Delegates.** Subagents get their own context for work that would otherwise
  fill the parent's.
- **Keeps working while you do not.** Gateway, scheduled jobs, background
  curation.
- **Talks where you are.** Discord, ACP, MCP — as server or client.

## What got fixed along the way

Real defects, found by using the thing rather than auditing it. No claim about
what other builds contain — these were costing *this* lineage, quietly:

- **Search stopped lying.** File search ran as a shell pipeline, so an invalid
  pattern came back as *no matches*. A search for `legacy_connect(` reported
  **0 hits where there were 5**. A tool that returns nothing looks exactly like
  a codebase that contains nothing.
- **The agent knows its own context size.** It reads the real window from the
  server instead of assuming 128,000, and re-checks it.
- **Plugins actually ship.** No package data was declared, so an installed copy
  carried no plugin manifests at all. Everything worked from a source checkout
  and silently vanished when installed.
- **Two functions that could never have run.** One imported a helper that
  existed nowhere; the other used a name it never imported.

The clearest one: a single misconfigured field produced **73% of all logged
errors**, each retry burning 13–16K tokens. Nothing crashed. It just cost money
and made the model look slow.

---

## What it was tested on

One machine, everything running at once. The table at the top of this page is a
live snapshot, not a best case stitched together from separate runs.

Two inference servers and a memory engine, with 924 MB left over. The helper
model runs entirely on the CPU and still holds 200 MB of graphics memory — the
price of being on the same machine at all. It earns that back by never making
the main model wait: background work runs *beside* your turn instead of after
it.

**Every tuned number here is tuned for that box.** They are written down with
the reason next to them, so you can redo the arithmetic for yours rather than
copying values that will not fit:

| setting | why this number |
|---|---|
| KV pool 2048 MB | what fits beside 10 GB of weights on a 16 GB card |
| context 131,072 | 9.1 GB of conversation in system RAM, which 31 GB can hold |
| compaction at 116,000 | the window, minus thinking budget, minus reserve |
| thinking budget 12,000 | measured: answers land between 150 and 2,400 tokens |
| helper model, thinking off | with thinking on, a 1.7B model spends its entire output budget reasoning and returns an empty answer. 24 seconds for nothing, against 2.6 with a result. |

Move to a different card and every one of them changes.

---

## Getting it

`./install.sh` installs the `daedalus` command and creates `~/.daedalus/`.
`daedalus setup` walks the first run.

The inference side — fetching and building llama.cpp, pulling the weights,
running both servers — is `scripts/stack.sh`. It writes its own config on first
use and `scripts/stack.sh doctor` tells you what is missing on your machine.

That is the mechanics. It is not what this page is about.

## Where it came from

Forked from Hermes Agent **0.8.0**, which was the high-water mark and earned it.
What came after was accumulation rather than continuation: tool surfaces and
skill catalogues grew, and none of that is free when every name sits in the
prompt on every turn.

This fork inverts the priority. Intelligence per token. Nothing shipped that is
not maintained.

> This repository starts at a single commit. That is deliberate, not a lost
> `.git` — the fork diverged far enough that upstream ancestry was misleading
> rather than useful. Upstream stays
> [NousResearch/hermes](https://github.com/NousResearch/hermes), MIT, and the
> licence travels with the code.

It ships without credentials. Keys, tokens and config are runtime state, kept
out of the repository, with `.example` templates in the tree. It also does not
share a namespace or a home with Hermes, and never reads `HERMES_HOME` — a
fresh install cannot inherit another agent's state.

## Licence

MIT, upstream Nous Research. See [LICENSE](LICENSE).

---

## The rest of it

Daedalus runs on Android, unrooted. Podroid provides the container, Alpine runs
inside it, the agent lives there. Not a remote agent with a phone client: the
app talks to it over loopback, prefers it whenever it answers, and falls back to
a paired desktop only when it does not. The model can still come from the
machine you paired with. The *agent* is what lives in your pocket.

**We do not pinky-promise that your data stays yours — there is nowhere else for
it to be.** No central server, no account, no copy on our side to leak, sell or
hand over. That is a design position, not a policy page, and we wrote it down
before building on it: **[On Local-First Data
Sovereignty](https://mazemaker.online/manifesto/)**, April 2026, unchanged
since.

None of this started here. **remainder.online** was engineered first;
**mazemaker.online** and **mazemaker.dev** came after. Then rinse and repeat.
Every piece is scar tissue — north of a **trillion tokens** spent finding out
what breaks, turned into what it became. What survived is what stopped breaking.

**Iris** — the god of messages — grew up beside it rather than after it. Still
in private testing; ships in **The Box**. That is all we will say here.

The labyrinth got built. The minotaur got banned. That imploded the entire
matrix, which is how we found the next door.

More soon:tm:
