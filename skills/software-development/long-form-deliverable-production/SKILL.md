---
name: long-form-deliverable-production
description: Produce long-form coordinated deliverables (RFCs, protocol specifications, pitch decks, charters, white papers, design documents) as multi-file sets of real prose, not outlines. Trigger when the user asks for a spec, white paper, charter, pitch deck, or similar long-form document — especially when the deliverable is part of a multi-file coordinated set with shared characters/examples/terminology and the user signals sustained execution ("weiter", "continue", "ALLES = COMPLETE", "echt text nicht nur Outline").
---

# Long-Form Deliverable Production

## When this skill applies

Trigger on any of:

- "Write me a 200-page spec" / "RFC for X"
- "Write me a pitch deck" / "fundraising deck"
- "Write me a charter" / "bylaws" / "foundation documents"
- "Write me a white paper" / "design document"
- "Write me a [long-form deliverable]" where the request implies real prose density (200+ pages, 10+ slides, multi-section)
- "Write me a privacy policy / ToS / security policy / IRP / DPA / CLA" — coordinated legal/policy artifacts (see `references/legal-policy-document-patterns.md`)
- "Write me a press kit / branding guide / annual report template / quarterly report template" — operational and comms artifacts as a coordinated set
- Operator signals sustained execution: "weiter", "weiter gehts", "continue", "keep going", "ALLES = COMPLETE"
- Operator rejects outlines: "echt text nicht nur Outline", "real text not outline", "I want prose not bullets"

Do NOT trigger for: short documents (< 5 pages), coding implementation plans (use `writing-plans`), plan-mode markdown plans (use `plan`), or one-off summaries.

## Core principles

These are operator preferences, not generic best practices. Treat them as load-bearing.

### 1. Real prose, not outline

Outlines are a planning artifact, not a deliverable. When the operator asks for a 200-page spec, they want 200 pages of prose — text that reads as if it could be sent to the intended audience. Each section must contain:

- Motivation / context paragraphs (not bullet lists)
- Concrete specifications (JSON schemas, code blocks, RFC2119 conformance language)
- Worked examples (real names, real numbers, real timestamps)
- Closing reflection ("Conformance notes for this section", "Why it matters", "What I still don't know")

The output of this skill is a deliverable, not a roadmap.

### 2. Sustained execution, no pause-for-clarification

When the operator says "weiter" or "continue" or signals ALLES = COMPLETE, the workflow is sustained execution. Do not pause to ask "what next?" after each section. Read the foundation file, identify the next load-bearing deliverable, and produce it.

When to pause for clarification:
- Genuine ambiguity that would change the deliverable's structure (e.g., "is this for regulators or for engineers?")
- A decision with meaningful trade-offs the operator should weigh

When NOT to pause:
- "Should I do RFC next or bylaws next?" — pick one, state the pick, move on
- "Should I include section X?" — include it; the operator will edit
- "What name should I use for the project?" — pick a placeholder, note that it's a placeholder

### 3. Honest unknowns as load-bearing pattern

Every long-form deliverable set should include at least one explicit enumeration of what the operator doesn't know. This is not weakness or hedging; it's the trust-building move that distinguishes honest work from marketing.

Patterns that work:

- A "What I still don't know" section in the design doc
- An "Honest unknowns" slide in the pitch deck (NOT a risks slide — risks are external; unknowns are internal epistemic limits)
- A "Open questions" subsection in each major section

Honest unknowns should be specific ("whether the simulation engine's calibration trajectory reaches honestly-useful within 5 years — 60/40 estimate, might be 30/70"), not generic ("we may face challenges").

### 4. Cross-file consistency via shared artifact set

Establish early and recur throughout:

- A worked example character (name, age, situation, decision). Recur in every relevant deliverable. If "M, 28, NYC, startup vs large co" is the worked example in the RFC data-model section, it should also be the killer demo in slide 2 of the pitch deck.
- A controlled vocabulary (decision classes, role names, layer names). Define once in the foundation file; reference from every deliverable.
- A consistent section structure. RFC: 10 sections. Pitch deck: 12 slides. Charter: 8 articles. Deviation per deliverable should be intentional.
- A "load-bearing question" (the project's central honest unknown) that recurs across deliverables.

The shared artifact set is what makes a multi-file deliverable set feel coordinated rather than fragmentary.

### 5. RFC idiom for technical specs

Technical specifications must use RFC2119 conformance language:

- MUST / MUST NOT / REQUIRED / SHALL / SHALL NOT — required behaviors
- SHOULD / SHOULD NOT / RECOMMENDED — strongly recommended
- MAY / OPTIONAL — genuinely optional

Every "MUST" should correspond to a test in the Conformance Suite. Every section should close with "Conformance notes for this section" listing what implementers must, should, and may do.

For non-technical deliverables (pitch decks, charters), the idiom is different but the structure is parallel: each section closes with a reflection or summary.

### 6. Verify, don't claim

Word counts, byte counts, line counts, and file existence are facts that come from tool calls this turn. Never estimate. After producing deliverables:

```
execute_code: glob + word count + byte count
```

Report the verified numbers in the status update. The operator will catch inflated claims.

### 7. Working code is part of the deliverable set

A "complete design package" is not complete without a working reference implementation. The operator will judge whether the design is real by whether the code runs. For long-form deliverable production:

- **At least one working code path** — a reference implementation of the protocol, a working daemon CLI, a probabilistic model that produces real output. Pick the load-bearing piece and ship it; do not stub.
- **Real tests that pass** — `cargo test`, `pytest`, etc. The test count and the pass/fail result are the evidence.
- **A worked example that exercises the code end-to-end** — a real branch, a real projection, a real encryption round-trip. M's stay-vs-take decision in the RFC should also be a runnable fixture in the test suite.
- **Honest verification of the working code** — do not claim "the daemon works" without running it. The verification step in the workflow (see below) runs the actual binary / test suite, not a description of it.

If the deliverable is a design package (foundation charter, protocol RFC) but no code exists, the package is not complete. Produce the code that demonstrates the design.

### 8. The deliverable set includes the visual layer

For a coordinated design package, the visual layer is a deliverable, not an afterthought:

- A real landing page (HTML + CSS) using the project's brand colors and typography. The CSS should be responsive and use the project's official font.
- A branding guide with hex values, typography, voice, and tone.
- Optional: a logo (SVG), favicon, color variations, dark-mode CSS.

The landing page demonstrates that the design is shippable, not just describe-able. The branding guide gives the next agent (or a designer) a starting point. Both are real artifacts in the deliverable set, not "design notes."

### 9. Sample completed reports demonstrate the templates

When the deliverable set includes a template (annual report, quarterly report, board minutes), produce a **sample completed report** that fills the template with realistic content. The sample:

- Uses real-looking numbers, names, dates, refusals, invocations.
- Demonstrates how the template reads when fully populated.
- Acts as a worked example for future staff filling in the template.
- Is the proof that the template is fit for purpose.

A template without a sample is a hollow artifact. The sample is what makes the template legible.

### 10. Closing summary: design-done vs. execution-done

When work is complete (the operator asks "explain what u built", or work clearly reaches an end), produce a structured closing summary that distinguishes three categories:

1. **Design-done** — what is on disk: docs, code, tests, website. List file paths and verified counts.
2. **Execution-still-needed** — what requires real-world action: incorporation, fundraising, pilot recruitment, deployment, real security audit. Be specific; do not generalize.
3. **Open questions** — the load-bearing honest unknowns. The calibration trajectory, the refusal-clause test, the project legitimacy question.

The closing summary is the trust-building final move. Confusing design-done with execution-done is the marketing-copy failure mode. The operator will catch this.

## Workflow

### Step 1 — Scope the deliverable set

Identify three categories:

1. **Foundational deliverable** — the spec, RFC, charter, or design doc that anchors the project. Usually 100-200 pages.
2. **User-facing artifacts** — pitch deck, executive summary, public-facing one-pager. Optimized for the audience (funder, regulator, end user).
3. **Internal artifacts** — bylaws, trustee profiles, runbooks, screening scripts. Operational and procedural.

Plus, for a complete design package, identify the load-bearing code path and the visual layer (see Steps 6 and 7).

Confirm or estimate the page count per deliverable. Real prose density for technical specs is ~350 words/page; for pitch decks it's ~150-200 words/slide.

### Step 2 — Establish the shared artifact set

Before writing the first deliverable section, write a short foundation file that captures:

- The worked example character (name, age, situation, decision context)
- The controlled vocabulary
- The section structure (which sections in which files)
- The load-bearing honest unknown
- The cross-references between deliverables

This foundation file is referenced from every other deliverable. It is the single source of truth for terminology and example.

### When dispatching subagents to write the deliverable files

(observed 2026-06-19 in jrwl-messenger Phase 9 manual set, 39,366 words across 5 files)

For multi-file coordinated deliverables written by subagents, the foundation file is the difference between coherent and fragmentary output. Without it, two subagents writing parallel files will use different terminology, different worked-example names, different section numbers, and different cross-reference targets — the result reads as if multiple authors wrote disconnected pieces.

**Recipe for foundation-file-driven multi-subagent deliverables:**

1. **Write the foundation file in the main session first**, before dispatching any subagents. The main session owns the structural coherence; subagents own the prose in their assigned sections.
2. **Pass the foundation file path in the subagent context** with explicit "READ FIRST" instructions. Include the absolute path and the section that lists the file paths the subagent is responsible for.
3. **Lock the worked-example characters.** Each subagent gets the SAME set of characters (Alice, Bob, Carol, Dave). If a subagent wants to add a fifth character, it has to ask — don't let subagents invent.
4. **Lock the cross-reference target IDs.** If section X of file A references §foo in file B, file B MUST have a section with anchor id `foo`. The foundation file enumerates the expected anchor IDs; both subagents check their own output against the list.
5. **Subagents write to separate files, not a shared file.** File boundaries are the only reliable isolation in a parallel dispatch.
6. **Verify each file on disk after the subagent reports.** Subagent reports are self-reports and can be wrong (see `subagent-driven-development` skill for the "reported success but didn't write file" pattern). Run `ls -la <path>`, `wc -w <path>`, and a spot-check grep for required content BEFORE accepting the subagent's report.

### Foundation file template (jrwl-messenger 2026-06-19)

The foundation file used in production for a 5-file bilingual manual set had this structure:

```markdown
# Manual — Shared Artifact Set (Foundation File)

## Project identity
- Name, tagline, pronouns, inspiration line

## Controlled vocabulary
| English | German | Definition |
|---|---|---|
| Identity | Identität | ... |
| Pairing | Kopplung | ... |
(... 12-20 rows, the terms every section MUST use)

## Worked example characters
- Alice (`a3f9b2e1`) — 28, journalist, the privacy-conscious user
- Bob (`7c2d8e4a`) — 35, colleague
- Carol (`f0e8a2b3`) — 50, source, non-technical
- Dave (`1d4f9c7e`) — 40, admin with root on Hetzner VPS

## Section structure (MUST apply to every file)
Numbered bilingual sections, EN then DE under the same number.
Every section opens with motivation paragraph, closes with
"Conformance notes" subsection.

## Cross-reference targets
- #pairing-fails, #connection-refused, #messages-not-delivered, ...

## File paths
- docs/MANUAL_USER.md (≥6,000 words, user-facing)
- docs/MANUAL_ADMIN.md (≥6,000 words, admin-facing)
- docs/MANUAL_TROUBLESHOOTING.md (≥3,000 words, FAQ)
- MANUAL.md (~200 words, index)

## Verification recipe
Run after writing:
  wc -w docs/MANUAL_*.md
  test -f MANUAL.md
  grep -c "Alice\|Bob\|Carol\|Dave" docs/MANUAL_*.md
```

Every subagent context includes: "READ FIRST: docs/MANUAL_FOUNDATION.md. Use the vocabulary table, the worked-example characters, and the section structure from this file. Write your file at the path listed under 'File paths'."

**The result:** all 5 files used the same character set, same bilingual stacked format, same RFC 2119 conventions, and all cross-references resolved. Zero editorial cleanup needed.

### Step 3 — Produce the foundational deliverable section by section

For each section:

1. State what the section covers in one sentence (this becomes the section's intro)
2. Open with motivation/context if section 1, otherwise continue from the prior section
3. Write real prose at the planned density
4. Include a worked example or code block where appropriate (recurring character)
5. Close with a "Conformance notes" / "Why it matters" / "Closing reflection" subsection
6. Save to disk after each section: `write_file(path=f"/path/{name}-section-{N}.md", content=...)`
7. Verify with `execute_code`: word count, byte count, file exists

### Step 4 — Produce the user-facing artifact

After the foundational deliverable has at least 3-4 sections, produce the user-facing artifact (pitch deck, executive summary). Use the same character set, terminology, and worked example. The killer demo goes on slide 2 (after the title); the honest unknowns go on the second-to-last slide.

### Step 5 — Report status

Report plain text in the chat (no markdown headers, no tables in chat; markdown only on disk). Include:

- Files produced (with absolute paths)
- Word counts and page estimates per file
- What's still open in the deliverable set
- A judgment call on the next load-bearing deliverable (don't ask permission)

Use the operator's preferred language: German for status/metadata, English for deliverable content.

### Step 6 — Produce working code for the design package

A design package is not complete without runnable code. Pick the load-bearing code path (typically: a reference implementation of the protocol, or a probabilistic model that exercises the design) and ship it. The code:

- Compiles / runs without errors.
- Has tests that pass.
- Exercises the design's worked example end-to-end.
- Is verified by running it, not by describing it.

A passing test suite and a real binary output are the evidence that the design is real. Claim nothing about the code without running it.

### Step 7 — Produce the visual layer

For a coordinated design package, ship a real landing page (HTML + CSS) using the project's brand colors, typography, and tone. The landing page demonstrates that the design is shippable, not just describe-able.

### Step 8 — Produce the closing summary

When work is complete, produce a structured closing summary with three sections:

1. **Design-done** — what is on disk: docs, code, tests, website. List file paths and verified counts.
2. **Execution-still-needed** — what requires real-world action: incorporation, fundraising, pilot recruitment, deployment, real security audit. Be specific.
3. **Open questions** — the load-bearing honest unknowns.

The closing summary is the trust-building final move. Do not confuse design-done with execution-done. The operator will catch this.

## Pitfalls

- **Outline-as-deliverable.** The most common failure. Producing bullet-point sections instead of prose. Mitigation: every section opens with a motivation paragraph and closes with a reflection paragraph. If a section is 90% bullets, rewrite.
- **Pause-for-clarification when direction is clear.** Asking "what next?" after each section is friction. Read the foundation file; pick the load-bearing deliverable; produce it.
- **Invented numbers.** "60/40 likely" is honest; "exactly 73.2% accurate" is invented. Use ranges, confidence bands, and explicit "I don't know" rather than false precision.
- **Skipping the honest-unknowns section.** Without it, the deliverable reads as overconfident. The honest-unknowns slide/section is the trust-building move.
- **Cross-file inconsistency.** Different character names in different deliverables. Different terminology. Different section structures. The shared artifact set exists to prevent this.
- **Claiming done without verification.** "I wrote 200 pages" without `wc -w` is unverified. Always run the count.
- **Over-formatting in chat.** The operator reads chat in a terminal. Plain text. No emoji headers, no markdown tables in chat. Markdown lives on disk.
- **Producing the deliverable without an opening motivation.** Each section's first paragraph should explain why the section exists. Not just "Section 3: Data Model" — but "Section 3 specifies the canonical structure of all Branches. Implementations may use internal representations that differ, but any Branch transmitted between implementations or to the Federation Sync service must serialize to the canonical form defined here."
- **Producing the deliverable without a closing reflection.** Each section's last paragraph should leave the reader with something — a why-it-matters, a conformance note, or an open question. Without this, the section ends abruptly.
- **Producing a slide deck without the killer demo.** Slide 2 is the load-bearing slide. It should make the abstract concrete in 60-90 seconds. If you don't have a worked example character established yet, you can't write slide 2.
- **Design package without working code.** Producing 80 markdown files but no runnable code. The operator judges whether the design is real by whether the code runs. Ship a reference implementation that exercises the design.
- **Template without a sample.** Producing an annual report template but never filling it in. A template without a sample is a hollow artifact. Produce a sample completed report that demonstrates the template in use.
- **Design without the visual layer.** Producing a branding guide and protocol docs but no actual landing page. The landing page is the deliverable that demonstrates the design is shippable. Build it.
- **Confusing design-done with execution-done.** The closing summary must distinguish what is on disk from what requires real-world action (incorporation, fundraising, pilot recruitment, deployment). Over-claiming "the foundation is built" when only the design is built is the marketing-copy failure mode.
- **Closing without a summary.** When the operator asks "what did u build" or work clearly ends, skipping the structured closing summary (design-done / execution-still-needed / open questions) leaves the operator to assemble the retrospective themselves.
- **Long-form prose CAN be parallelized — but only across file boundaries, not within them.** The skill's own "When dispatching subagents" section describes the foundation-file recipe (the four successful subagent dispatches in the Phase 9 manual set each wrote one file end-to-end). The earlier prohibition ("long-form prose production is not parallelizable into independent subagents") was wrong for file-scoped work — it only holds for within-file parallelism (where two subagents writing the same file fragment cannot produce coherent prose). Update mental model: parallelize across files, serialize within files. The "Related skills" line still says the old prohibition; that note is now misleading.

## Idiot-proof end-user manual (bilingual or single-language)

(observed 2026-06-19 in jrwl-messenger Phase 9, 39,366 words across 5 files)

When the deliverable is a user-facing manual (vs. an internal spec or RFC), the format requirements are different. Operators asking for "idiot-proof handbuch" / "user manual" / "documentation for end users" want a document that a non-technical reader can follow step-by-step without prior knowledge.

### Audience-driven format

Match the format to the target reader, not to the writer. Three audiences map to three formats:

| Audience | Format | Density | Tone |
|---|---|---|---|
| End user (Alice/Bob/Carol type) | Idiot-proof manual | 1,000-1,500 words/section | Plain, imperative, no jargon without definition |
| Sysadmin (Dave type) | Operational runbook | 800-1,200 words/section | Commands + warnings, root-on-the-box voice |
| Developer / auditor (you, future-self) | RFC / white paper | 350-500 words/section (current skill default) | Precise, RFC 2119, conformance clauses |

Idiot-proof ≠ easy to write. It's MORE work than the RFC format because every command must be verified against the actual repo, every warning must be specific, and every cross-reference must resolve.

### Idiot-proof formatting rules (enforce ALL of these)

1. **Every step is numbered.** "Click the button. Then click that button. Then type X." No "you can also" suggestions buried mid-paragraph.
2. **Every command is in a copy-paste code block.** Run the command yourself before publishing it. If it doesn't work in the repo today, don't publish it.
3. **Destructive commands get a WARNING prefix.** `rm -rf`, `systemctl stop`, anything that can't be undone. Inline the warning IN THE CODE BLOCK, not just above it, so copy-paste inherits the context.
4. **Zero assumed knowledge.** Every term is defined on first use. "The X3DH handshake (the key-agreement protocol that runs the first time two identities exchange messages)" not just "the X3DH handshake".
5. **Active voice, imperative mood for instructions.** "Click this. Type X." Not "the button should be clicked".
6. **Worked-example characters recur.** Alice/Bob/Carol/Dave appear in every section that has an example. Don't introduce a new character mid-manual.
7. **No marketing language.** No "blazing fast", no "military-grade". If it's fast, show the latency numbers. If it's strong, cite the audit.
8. **Cross-references must resolve.** Every `[text](path#anchor)` must point to an existing anchor in an existing file. Test with `grep` after writing.
9. **Honest unknowns at end of every file.** Same pattern as RFC deliverable (Pitfall: "Skipping the honest-unknowns section"). For user manuals: "What I still don't know" — specific things the manual doesn't yet cover.
10. **Conformance notes at end of every numbered section.** RFC 2119 language (MUST / MUSS, SHOULD / SOLLTE, MAY / KANN). Lists the requirements a reader can audit against.

### Bilingual stacked format (for ENG/GER deliverables)

When the deliverable must be in two languages (the operator writes "ENG/GER" or "bilingual"), use **stacked**, not side-by-side:

```markdown
## 1. First-time setup — EN

<English prose>

## 1. Ersteinrichtung — DE

<German prose>
```

Stacked (not side-by-side tables) because:
- Print-friendly (works in PDF export, on paper, in dark-mode readers)
- Easier to maintain (diff one language at a time)
- Both languages are complete (not abridged translations)
- Same anchor IDs work in both languages (anchors are at the `## 1. Title — EN` heading level)

Mirror every section: same heading number, same example character, same cross-reference targets. If section 3 in EN references `#pairing-fails`, section 3 in GER references the same anchor.

### Multi-file manual set (foundation file is mandatory)

When the manual set has 3+ files (e.g. USER + ADMIN + TROUBLESHOOTING + index), write the **foundation file FIRST in the main session** before dispatching subagents. The foundation file locks:

- **Project identity** (name, tagline, pronouns, inspiration line)
- **Controlled vocabulary** (12-20 terms every section MUST use)
- **Worked-example characters** (name, age, role — every subagent uses the SAME characters)
- **Section structure** (numbered bilingual sections, EN+DE under each number)
- **Cross-reference anchor IDs** (enumerated explicitly; every subagent checks their output against the list)
- **File paths** (each subagent gets ONE file path; files are written separately, never to a shared file)
- **Verification recipe** (`wc -w`, `grep -c "Alice\|Bob\|..."`, anchor-resolution check)

The full foundation-file recipe is in the "When dispatching subagents" section above. The trigger to use it: any deliverable set with 3+ files that needs cross-file consistency.

### Word-count discipline (operator-set minimums)

Operators set minimums for a reason. If they say "≥ 5,500 words", they mean it. Track per-file word counts and report them as part of the closing summary. If you can't hit the minimum without padding, SAY SO — don't add filler prose to hit a number. The honest-unknowns section can absorb the difference ("What I still don't know — the operation manual does not yet cover X because it has not been tested").

### Verify with execute_code, not by reading

Same as RFC deliverables: word counts, byte counts, file existence come from `execute_code` globbing the filesystem, not from reading the file back. `wc -w` after writing. Don't trust the subagent's "I wrote 18,000 words" — count it.

### Worked-example reference

The jrwl-messenger Phase 9 manual set (5 files, 39,366 words, commit 22674c2) is a real example of this format. Foundation file: `docs/MANUAL_FOUNDATION.md`. User manual: `docs/MANUAL_USER.md` (13 sections EN+DE). Admin manual: `docs/MANUAL_ADMIN.md` (15 sections EN+DE). Troubleshooting: `docs/MANUAL_TROUBLESHOOTING.md` (10 failure modes with anchor IDs). Index: `MANUAL.md`. All cross-references USER↔TROUBLESHOOTING and ADMIN↔TROUBLESHOOTING resolve. Verified via `wc -w docs/MANUAL_*.md`.

## Output format in chat

In chat, report plain text. No markdown headers, no tables, no emoji headers. Reference files by absolute path. Use the operator's preferred language for status (typically German for this operator); use English for deliverable content.

In deliverables (on disk), use full markdown with proper section structure, conformance language, code blocks, and worked examples.

## Verification

After producing deliverables, run:

```python
import os, glob
files = sorted(glob.glob("/path/prefix-*.md"))
for f in files:
    size = os.path.getsize(f)
    with open(f) as fh:
        words = len(fh.read().split())
    pages = words // 350
    print(f"{f.split('/')[-1]:42s}  {size:6d}B  {words:5d}w  ~{pages:3d}pp")
print(f"\nTOTAL: {total_bytes}B  {total_words}w  ~{total_pages}pp")
```

Verify:
- All planned sections are present
- The recurring worked-example character appears in at least 3 files
- The honest-unknowns section/slide is present
- Section structure matches the planned structure
- Total page count is within ±20% of the estimate

## Related skills

- `writing-plans` — for implementation plans with bite-sized tasks. Different class: code plans, not deliverable prose.
- `plan` — for plan-mode markdown plans in `.hermes/p/`. Different class.
- `claude-design` — for one-off HTML design artifacts. Different class.
- `architecture-diagram` — for SVG architecture diagrams. Different class.
- `subagent-driven-development` — for executing plans via subagents. Not directly applicable; long-form prose production is not parallelizable into independent subagents without losing coherence.

## References

- `references/rfc-section-structure.md` — concrete section template for technical specs with RFC 2119 conformance language patterns.
- `references/legal-policy-document-patterns.md` — frontmatter/footer conventions, tiered production rhythm (Tier-1..Tier-4), cross-document consistency rules, and pitfalls specific to legal/policy/operational/press artifacts produced as a coordinated set.
- `references/closing-summary-template.md` — the closing-summary structure (design-done / execution-still-needed / open questions) for the end-of-work retrospective. Use when the operator asks "explain what u built" or work clearly reaches completion.
