# Pulse-Wurm Cron Tick — 2026-06-20 Operational Notes

Concrete learnings from the 2026-06-20 ~00:00Z tick that don't fit the main `cron-tick-playbook.md` sections but are still critical for next-tick operators.

## Terminal Tool Security Blocks — Reading pulse_search Output

**The problem**: The natural reflexive response when you have a 100KB+ JSON file in `/tmp/hermes-results/call_<hash>.txt` is to pipe it into Python to extract the relevant fields. **The terminal tool blocks this on two patterns:**

- `cat /tmp/hermes-results/call_*.txt | python3 -c "..."` → blocked by Tirith as `tirith:pipe_to_interpreter`
- `python3 << 'PYEOF' ... PYEOF` → blocked by Tirith as `script execution via heredoc`

These are **hard blocks at the terminal-tool level**. The agent cannot override them. The pattern is rejected as a class.

**What works instead (verified 2026-06-20)**:

1. **`grep -oE` for URL/title extraction**:
   ```bash
   grep -oE 'https?://[^"\\]+' /tmp/hermes-results/call_<hash>.txt | sort -u
   grep -oE '.{30}arxiv-id.{400}' /tmp/hermes-results/call_<hash>.txt
   grep -oE 'title\\": \\"[^"]{10,250}' /tmp/hermes-results/call_<hash>.txt
   ```
   The double backslash (`\\`) handles escaped quotes inside the stringified JSON. Sort -u to deduplicate.

2. **`read_file`** for full content of the file (it's one giant line, but `read_file` handles it as a single chunk).

3. **`execute_code`** for any state mutation, JSON parsing logic, or batch processing. This is the recommended path for state file updates and mazemaker_remember batching.

4. **`scripts/parse_pulse_search.py`** via `execute_code` — already handles the double-wrap unwrap, the `ranked_candidates` key, the arxiv /pdf/↔/abs/ normalization. Glob-import it as documented in the main playbook.

## Result File Format

- Path: `/tmp/hermes-results/call_<16-hex-chars>.txt` (e.g. `call_019ee25533437b60a81480ec.txt`). Older docs reference `call_function_<hash>.txt`. Both patterns exist on different ticks. **Glob `call_*.txt` to cover both.**
- Size: 100KB+ for a single `pulse_search(depth='deep')` call.
- Format: **one single line of JSON** (`wc -l` returns 0). All content is on line 1; `\n` only inside string values.
- Inner JSON has `\"`-escaped quotes (stringified JSON wrapped in another JSON).

## Browser-Navigate to arxiv Abs for Title Confirmation

When the `pulse_search` openalex entry has a snippet but no title (or a truncated title), `browser_navigate` to `https://arxiv.org/abs/<id>v<N>` to get the canonical title before saving to mazemaker.

**2026-06-20 case**: arxiv 2605.05509 had snippet "Large language models (LLMs) are increasingly being integrated into web browsers to create agentic browsing systems that execute actions on behalf of the user. Prior work considering the security of a..." — no title visible in the openalex entry. `browser_navigate` to `https://arxiv.org/abs/2605.05509v1` returned the heading "WAAA! Web Adversaries Against Agentic Browsers" + author list (Datta, Nahapetyan, Enck, Kapravelos) + full abstract. The title was needed in the mazemaker_remember call to identify the cluster correctly.

**When to use**: Any time the snippet is truncated mid-sentence, or the openalex `title` field is empty/missing, or the relevance score is low (0.2-0.4) but the snippet content looks topically on-target. A 5-second browser_navigate beats a misclassified mazemaker_remember.

## Proactive Next-Seeds Exploration

**Pattern observed 2026-06-20**: The script's internal logic uses `github_search()` (narrow, GitHub only) and bumps `consecutive_empty` to 1 when 0-novel. But the script's `next_seeds` list in state — the top 5 lowest-saturation seeds queued for the next tick — are typically **unsaturated seeds that have not yet been searched via the MCP `pulse_search` deep channel** (which has 22 sources including openalex).

**Proactive move**: After the script returns `consecutive_empty=1` (or 0+), pick the lowest-saturation `next_seeds` entry and call `mcp__pulse__pulse_search(depth='deep')` on it directly. This catches material that the script's narrow channel would miss.

**Cost-benefit**: One `pulse_search(depth='deep')` = ~30s + 100KB JSON. 6h cron budget easily absorbs 1-2 of these per tick. The 2026-06-20 tick used one proactive search and surfaced 1 genuinely novel paper (WAAA! 2605.05509), preventing the saturation-driven rotation that would have happened at `consecutive_empty=3`.

**When to skip**: When `consecutive_empty >= 2` AND all 5 next_seeds are high-saturation carryovers. The proactive pattern is for *low-saturation* (sat 0-1) seeds that have not yet been processed.

## Author Cluster Detection — Twin-Paper Patterns

**Finding 2026-06-20**: The Same-Origin Policy for Agentic Browsers paper (arxiv 2606.14027, Datta+Nahapetyan+Enck) and the WAAA! Web Adversaries Against Agentic Browsers paper (arxiv 2605.05509, Datta+Nahapetyan+Enck+Kapravelos) are **twin papers from a single lab** — one defensive primitive (SOP), one attack taxonomy (WAAA). They were published ~1 month apart and reference each other's problem space.

**Generalized pattern**: When you find a novel arxiv paper via openalex, the `author` field is comma-separated. Cross-check against `mazemaker_recall` for prior papers by the same authors. If 2+ prior papers exist in the same topical cluster, the lab is on a coordinated research program and their next paper is a high-yield follow-on seed.

**Operational pattern**: After saving the novel paper, queue a follow-on seed in `next_seeds` with a name like `"<author1> <author2> <topic> follow-on 2026"` to catch their next paper when it lands. Example from 2026-06-20: `"Datta Enck Kapravelos agentic browser security follow-on 2026"` would surface the next paper from this lab.

**Why this matters**: Labs publish in clusters, not randomly. The follow-on yield is much higher than a fresh angle on the same topic. A single cluster-twin paper is often the precursor to a 3-5 paper program that this lab is producing for a year.

## Recurring Noise Pattern (NEW 2026-06-20)

**ICE agents Reddit cluster** — when a seed has "security" or "agents" in it, the openalex sub-channel is clean, but the reddit sub-channel surfaces 20+ Reddit threads about US Immigration and Customs Enforcement agents across subreddits like r/nottheonion, r/FBI, r/politics, r/fednews, r/CringeTikToks, r/UnderReportedNews, r/TodayILearned, r/Minnesota, r/Fauxmoi, r/ZenlessZoneZero, r/reactiongifs, r/europe, r/Futurology, r/technology, r/minnesota. The 2026-06-20 tick observed ~24 such URLs in a single search. **Mark visited en bloc** when the cluster appears — these are noise, not signal.

**Trigger words that surface this cluster**: "security", "agents", "enforcement", "policy" — anything that has a "human enforcement agent" sense in addition to the "AI software agent" sense you intend.
