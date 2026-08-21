# Closing Summary Template

Use this template when the operator asks "explain what u built", or when the deliverable set is clearly complete. The closing summary is the trust-building final move. Do not skip it.

The summary distinguishes three categories: design-done, execution-still-needed, and open questions. The first is on disk and verifiable. The second requires real-world action and is the operator's work, not the agent's. The third is the load-bearing honest unknowns that the design itself admits.

---

## Structure

### 1. Design-done

State what is on disk. Use verified counts from `execute_code` (file paths, byte counts, word counts, test counts). Do not estimate. Do not pad.

```
Conformance (Rust): 19 tests passing, ~5,500 LOC.
Daemon (Rust): binary builds, paths/store module works end-to-end.
Constraint layer (Python + Pyro): 8 tests passing, runs M's worked example.
RFC v0.1: 10 sections, ~23,000 words, ~70 pages.
RFC v2.0-draft: 11,500 words, ~33 pages.
Legal stack: 22 documents, ~85,000 words.
Operational templates: 8 documents, ~30,000 words.
Press & comms: 5 documents, ~25,000 words.
Technical ops: 8 documents, ~50,000 words.
Landing page: HTML+CSS, responsive, brand colors, hero with 3-layer SVG.
```

The numbers come from this turn's tool calls. `wc -l` and `find` in `execute_code`. State the verified path, not the deliverable name.

### 2. Execution-still-needed

State what requires real-world action. Be specific. The operator is the actor here; the agent is the designer's tool.

```
Not done, requires real-world action:

- The Foundation is not incorporated. That requires a Swiss lawyer
  filing in Geneva. The charter exists on disk; the legal entity does not.
- The funding is not committed. Grant application templates exist,
  but no actual money has moved.
- The pilots are not active. The Navajo agreement is "signed" in the
  sample Q4 report, not in reality.
- The code is a working prototype, not a production system. The Rust
  daemon has the path layout and storage, but no full HTTP server yet.
- The website HTML is not deployed. It is a static file in the repo.
- I have not done a real security audit. The docs reference "the most
  recent audit" with a placeholder auditor name.
- The post-quantum migration is specified in RFC v2.0-draft but not
  implemented in the conformance suite.
```

The framing matters: "design is done, execution is the next phase." Not "we're done" — that is the marketing-copy failure mode.

### 3. Open questions

The load-bearing honest unknowns that the design itself admits. These are not weaknesses; they are the foundation's epistemic accountability. State them with the same specificity the design uses.

```
Three open questions remain load-bearing:

1. Will the simulation engine reach "honestly useful" within 5 years?
   Our estimate is 60/40 yes. The calibration dashboard is the
   instrument that will answer this question publicly.

2. Can the calibration dashboard sustain public scrutiny? The dashboard
   publishes the gap between what the engine predicted and what
   actually happened. The dashboard's methodology is published in
   advance; the metrics are computed by an independent auditor; a
   30-day public comment period is open after each quarterly update.

3. Should the project exist at all? The refusal posture may cause
   the Foundation to lose funding or face legal challenges. The
   Foundation prefers this. The question is open, and the design
   refuses to hide that.
```

The honest unknowns are the trust move. Skipping them makes the summary read as overconfident.

---

## What to AVOID in the closing summary

- **Padding with affirmations.** "I'm proud of what we built" — cut. The operator doesn't need encouragement; they need a clear retrospective.
- **Re-listing the deliverable set in detail.** The operator saw each batch land. The summary recaps the categories and the verified counts, not every file.
- **Invented metrics.** "The Foundation has 1,247 active users" is in the sample Q4 report because that report is a worked example, not because the users exist. In the closing summary, distinguish the design (where 1,247 is plausible) from reality (where 1,247 does not exist).
- **Hiding the open questions.** A closing summary that lists "what was built" without "what is unknown" is the same marketing-copy failure mode the honest-unknowns slide is designed to prevent.

---

## Tone

Plain text. No markdown headers. No tables. The operator reads the closing summary in a terminal. Reference files by absolute path. German for status, English for deliverable content (per operator preference).

The closing summary should be the most honest paragraph the agent writes in the session. If the agent has to hedge, hedge. If the agent has to admit something is not done, admit it. The closing summary is not the place to over-claim.
