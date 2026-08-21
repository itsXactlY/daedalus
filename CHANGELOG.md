# Changelog

Versioning is the Hermes release this descends from plus a distribution tag.
PEP 440 requires a normalisable string, so package metadata reads
`0.8.1+daedalus`. `0.8.1-Daedalus` is the name.

---

## [0.8.1-Daedalus] — 2026-08-19

Carried forward from the Hermes **0.8.0** build — the one that was worth
keeping — and everything done to it since.

**This is half the machine.** Read the arc below and the dependency is
unmistakable: the central change was teaching the agent to *stop carrying its
own history*, and everything after it is either an exploitation of that or a
repair of something that had silently relied on the opposite. Take Mazemaker
away and you are not running a leaner agent — you are running one engineered to
forget, with nothing remembering for it. The `un-lobotomize` commits below are
what that looks like from the inside.

The full shape is still arriving: history moving in and out of Mazemaker
continuously, with a purpose-finetuned router choosing what returns. The router
works. The round-trip is not complete. Running it as intended requires Mazemaker
Pro+ (mazemaker.online).

---

## The arc

### Strip to a base worth building on

It started by throwing things away: a super-clean base, no browser stack, no
trash. Then `docker/` and `k8s/` went — neither had a single code reference.
Google Fire went with them, replaced by plain argparse with a
signature-derived parser. Stray config snapshots, duplicate plan directories
and skill assets followed.

The point was not tidiness. Everything left in a harness costs something on
every turn, and most of what shipped was never load-bearing.

### Make the agent stop carrying its own history
- (Simplified Work in Progress for Public Repository)

This is the change everything else rests on.

- **Soak + on-demand recall.** Every turn is written to Mazemaker as it
  happens, and pulled back when relevant.
- **Lean-context windowing** — *carry nothing, let Mazemaker carry it*.
- **Unslop the message history** — the transcript stopped travelling with the
  conversation; a pointer travels instead.
- **Session continuity.** New sessions seed from the pod rather than from
  scratch, including the prior session's tail and still-open goals, so
  restarting stopped meaning starting over.
- **Brain-readiness awareness**, so the agent knows whether its memory is
  actually there before relying on it.

Then the same idea applied to the prompt itself: the repo dev-guide was dropped
from runtime chats (**~4.5k tokens/turn**) and the skills index compacted to
names with lazy pointers (**~5.4k tokens/turn**). Ten thousand tokens a turn
that had been buying nothing.

### Un-lobotomize it

Carrying less exposed everything that had quietly depended on carrying
everything. A long run of fixes followed, and the commit titles are honest
about it — *un-lobotomize*, *stop the lobotomy*:

- memory guidance was never wired into the system prompt, so the agent had the
  tools and no idea it should use them
- bootstrap recall came back structurally empty — the compactor ignored the
  shape the pod actually returns
- resumed sessions lost the current user turn to compression, and recall timed
  out on top of it: textbook amnesia
- DeepSeek needed `reasoning_content` on *every* assistant message, including
  bootstrap tool-calls, or it rejected the request outright

### Route the recall
- (*Finetuning the router is work in progress - workaround is in place*)

Recall through the **Alice router** — a small finetune that picks *which*
memory call to make, so the main model doesn't spend its turn deciding. Landing
it took several passes: invalid router arguments now fall back to the parent
query, the router chooses tool *type* only and never overrides what was asked,
and multi-angle recall builds angles instead of resending the query. Shipped
with a systemd unit and a retrained router.

### Cut the messenger surface to Discord + ACP

Telegram and WhatsApp platform code was stripped out of the gateway and the
dead plugin directory deleted. The setup wizard, the gateway platform list and
the subcommand tables lost their entries. Stale adapter tests were archived —
Telegram DM-topics, Matrix websocket-auth retry, the end-to-end harness.
Discord was migrated onto the plugin/registry adapter path and the legacy
`gateway/platforms/discord.py` deleted.

**Why.** Every third-party bridge routes a conversation through infrastructure
somebody else owns and can read, log, subpoena or lose. That contradicts the
position this was built on — see
[On Local-First Data Sovereignty](https://mazemaker.online/manifesto/), written
April 2026 and unchanged since. A privacy stance and a WhatsApp bridge cannot
ship in the same product.

What replaces them is **Iris**: end-to-end encrypted P2P messaging, no central
server, no account, the phone itself being the server. Still in private
testing; ships in The Box.

### Take what was worth taking from 0.20.0

Not a wholesale upgrade — a cherry-pick, module by module, of what was actually
better: the memory-provider infrastructure, the CLI mixin architecture and its
dependency closure, `platforms/base.py` and `status.py`, `skill_utils.py`, and
the skill-lifecycle **curator** with its test suite. Sessions gained upstream's
new source fields.

### Give skills a life cycle

Skills stopped being a pile. **Bundles** load several under one command.
`SKILL.md` gained template variables and inline shell. Fifteen mega-skills were
split into a lean core plus `references/`, so loading one no longer drags its
entire appendix into the prompt. A deterministic auto-router picks skills with
usage telemetry behind it, the curator archives what has gone stale — while
protecting anything a bundle still references — and the index syncs into
Mazemaker so the agent can search skills the same way it searches memory.

### Harden it

`security audit` runs an on-demand OSV.dev supply-chain scan. Setup-time
installs are bounded and sandbox images provenance-checked. `doctor` gained
SSL/CA-bundle and SQLite WAL-reset checks with repair paths. Desktop
`connection.json` is created owner-only. Transient JSON/SSL/shape-mismatch
errors stopped being classified as permanent failures, and activity is touched
between tool results and the next API call so long turns stop looking idle.

---

## Fixed in this distribution

Defects found by *using* it. No claim is made about which exist elsewhere:

- **Search stopped lying.** `search_files` ran as a shell pipeline, so
  ripgrep's error exit was masked by `head` and an invalid pattern came back as
  *no matches* — 0 hits where there were 5, silently.
- **Context is known, not assumed.** Detection authenticates, reads the real
  window from the endpoint instead of a hardcoded 128,000, and re-checks on a
  timer rather than resolving once at startup.
- **`setup` stopped poisoning `.env`.** It wrote `DAEDALUS_MAX_ITERATIONS` into
  a file its own code reserves for secrets — and that variable outranks
  `config.yaml`, so `agent.max_turns` was decorative.
- **Plugins survive installation.** No package data was declared, so the wheel
  shipped no `plugin.yaml` for any plugin.
- **Two functions that could never have run** — one importing a helper that
  existed nowhere, one referencing an unimported name.
- **System services stopped writing the wrong home.**
- **Token accounting is honest** — reported from what the model read, not the
  billed subset, with real cost passed through.

## Independence

Own command, own modules, own `DAEDALUS_*` environment, own home.
`HERMES_HOME` is not read, so a fresh install cannot inherit another agent's
state or credentials. ~13,500 occurrences across 753 files. One word survives:
the tool-call parser registered as `"hermes"` — that is the Hermes-2-Pro *wire
format*, and models select it by that exact string.

No credentials ship. `auth.json`, `config.yaml`, `.env`, keys and tokens are
runtime state, gitignored, with only `.example` templates in the tree.

## Experimental — off by default

**Claude Code as the model backend.** Auth, per-model context windows and
isolation work; tool calling does not — turns intermittently return empty.
Disabled by default. Kept for the diagnosis: Claude Code is an agent, not a
completion endpoint, so tool calls must be negotiated as text and the model
improvises the format.

## Verification

Per-suite against the build this descends from, identical inputs: `agent`
5/1022, `tools` 103/2830, `cli` 8/351, `run_agent` 1/688, `daedalus_cli`
11/1544. Zero failures unique to this distribution.

A like-for-like run against `NousResearch/hermes-agent` — same model, same
task, both from scratch — is what settles it, and is not done yet.

---

*The old system is not discarded history. It is causal substrate.*
