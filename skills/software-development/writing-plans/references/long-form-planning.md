# Long-form planning notes

Captures operator preferences for **substantial / multi-page plans** — plans
that go beyond implementation detail into project architecture, concept
development, fundraising, or research design. Lessons distilled from a recent
multi-iteration planning session on a novel concept.

Use this when the deliverable is a long-form plan, not a bite-sized
implementation breakdown. For implementation-level plans, follow the umbrella
SKILL.md's existing structure.

## When to load this file

- The plan is more than ~1500 words
- The plan spans multiple layers (data model + simulation + governance + funding, etc.)
- The plan is for a project that doesn't exist yet (concept / pitch / RFC)
- The user asked for "100+ iterations" or "loop over N times"

## Required sections for substantial plans

When the plan is more than a simple implementation breakdown, the following
sections are non-negotiable. Missing any of them and the plan reads as
incomplete.

1. **Opinionated framing** — don't both-sides everything. Take a position. The
   operator reads plans for decisions, not balanced surveys. State the
   recommendation and the reasoning. "On the one hand / on the other hand"
   reads as evasive.
2. **Failure modes** — name them explicitly, not as polite "considerations."
   "Will probably fail because X" beats "may face challenges including X."
   Group by category (technical, social, governance, etc.). Concrete
   mitigations, not abstract watch-outs.
3. **Known unknowns** — a section that says "I don't know how to solve X, Y, Z"
   is more useful than faking completeness. The operator trusts plans that
   admit gaps. Phrase as "the three things I don't know how to solve" not
   "areas for further research."
4. **The killer demo / 60-second pitch** — why does this matter? What's the
   one story that makes the case in 60 seconds? Plans without a killer demo
   are unfundable. Write it as if you'd say it out loud, not as if it were
   a slide.
5. **Naming rationale** — when the plan introduces terms, propose 2-5
   alternatives with reasoning, then pick one. "X beats Y because..." with
   explicit tradeoffs.

## Iteration discipline ("loop over N" requests)

When the operator asks for "100+ iterations," "loop over N," or similar:

- Structure as **10 deep passes × 10-15 micro-iterations each** = 100-150
  iterations per round. (Or scale: 5 passes × 20, 20 passes × 5 — whatever
  fits the work.)
- Each iteration: **1-3 sentences describing the delta**. Terse. Code-style
  labels like `i.001: ...`, `i.002: ...` for traceability.
- Track iterations with consistent numbering across the whole set.
- **Skip iterations that don't produce a change.** Padding the count is worse
  than honesty. Document the count as "distinct iterations that produced a
  change," not "iterations attempted."
- After each pass, summarize what changed in that pass.
- At the end of all passes, a **synthesis section** with:
  - net-new structural changes
  - things that didn't change
  - what you're now more sure about
  - what you're now less sure about
- Save the full iteration set to a file (e.g.,
  `/home/alca/<project>-iterations.md`) and reference the path.

### Critical: do not stop to ask permission

After delivering the requested N iterations + synthesis + next-batches
list, the natural-looking move is "want me to do more?" **Do not do this.**

The operator's signal was direct: "why u stopping?" after 119 iterations.
The fix:
- End with what's still open + a "still going" signal
- Or end with the work, full stop
- Or, if there is genuine work still to do, just keep doing it
- **Never** end substantive iteration work with a permission-asking question

The same pattern applies to other deliverables: don't end a long plan with
"want me to go deeper on X?" End with what's still open as a flat list, or
just stop. Permission-asking reads as filler.

## Anti-patterns to avoid

| Pattern | Why it fails |
|---|---|
| Stop with "want me to do more?" | Operator reads it as stopping. Keep going or stop cleanly. |
| Both-sides framing | Reads as evasive. Take a position. |
| "Let's dive in" / "Here's what you need to know" | Tutorial-script tells. Start with the content. |
| Puffery: "testament," "pivotal moment," "underscores" | AI tells. Strip them. |
| Verbose section intros before the real content | Padding. Cut the intro. |
| "Despite challenges... continues to thrive" | Formulaic closer. Cut it. |
| "I hope this helps" / "Let me know if..." | Servile chatbot tells. Cut. |
| Hedging: "may potentially possibly..." | Cut. State the position. |
| Generic positive conclusions | Cut. State the next concrete step. |

The `humanizer` skill (bundled) has the full AI-tell list. Load it for
substantial prose.

## File-delivery pattern

For plans > 1500 words or with multiple passes:

- Save to `/home/alca/<project>-<artifact>.md` (or appropriate home path)
- Naming: `<project>-stack.md` for the main plan, `<project>-iterations.md`
  for iteration sets, `<project>-iterations-2.md` for second batches
- Present the substance in the response too — the file is for reference, not
  a substitute for the deliverable
- Reference the absolute path in the response. The user reads plans on disk
  as much as in-line.
- One file per deliverable. Don't co-mingle plan + iterations + cost
  analysis into one file.

## Plan-shape templates

| Plan type | Use this |
|---|---|
| Implementation plan, bite-sized tasks | Umbrella SKILL.md structure |
| Concept / project architecture | This file — long-form template |
| Fundraising / pitch | This file — heavy on killer demo, cost reality check, funding strategy |
| Research / methodology plan | This file — heavy on known unknowns, edge cases, validation approach |
| Quick decision | State decision + reasoning + alternatives considered + stop. No template. |

## Agent-role awareness

The operator is the **architect / observer**. When the operator asks the
agent to plan, the agent is acting as planner/architect, not as executor.
The agent should:

- Plan like an architect — opinionated, structural, holistic, with explicit
  position-taking
- Not defer decisions back to the operator — make them, with reasoning
- Surface what the operator would care about: cost, governance, capture risk,
  long-term survival, edge cases
- Not pre-implement or write code unless asked

The crew-execution model only applies when the operator is delegating
execution. When they're delegating planning, the agent plans fully and
hands back the plan.
