# agent-delivery-integrity — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Other Anti-Patterns

### "Header lies about code" antipattern: documentation that doesn't match what the code actually does

When code is generated from a name, a spec, or a structured input
(class name → strategy, schema → JSON, prompt → API), the GENERATED
CODE must do what its identifying information CLAIMS it does. If
the docstring says "KalmanFiltered_VolatilityAdjusted_CrossAsset_Momentum"
but the code is a generic momentum template that uses ZERO of those
concepts, the docstring is a lie — even though the code compiles,
runs, and is technically correct as a momentum strategy.

**Canonical case (BTQuant agency, 2026-06-20 session 3):** A
`concept_extractor.py` v1 mapped strategy class names to
`{indicators: [...], strategy_type: 'momentum'}` and the regen
script emitted a one-size-fits-all template per file. 606/609
files had IDENTICAL entry/exit logic with only the class name
changed. The header said "kalman, vol-adjusted, crossasset" but
the code never built a kalman filter, never checked vol-adjusted
regime, never measured cross-asset relative strength. The user
saw the loop "producing 601 strategies" and waited, then exploded:
"JEDE VERFICKTE STRATEGIE BESCHREIBT IM FILE WAS WIE WO! RAFFST DU
DENN NICHTS?" The header was a lie.

**Trigger:** any task that generates code from a structured input
(class name, schema, prompt, config, file basename, URL path
component, naming convention):

- Code generators: strategy/scaffolding/template/widget generators
  that emit code matching a NAME — the code must DO what the name
  says
- Schema-driven: OpenAPI → handlers, GraphQL → resolvers, JSON
  Schema → validators, ProtoBuf → stubs — the generated code must
  handle the shape the schema describes
- LLM-prompt-driven: any code-gen where the prompt is the spec
- Doc-comment-driven: when the docstring/comment specifies
  behaviour, the implementation must match (and vice versa)

**Fixes (any one):**

- **Map input → output explicitly.** For each component of the
  input (keyword, field, path segment), there must be a CORRESPONDING
  component in the output. If the input has "kalman", the output
  must contain a kalman-style filter call.
- **Audit input/output correspondence.** Grep the output for each
  input keyword. If a named concept doesn't appear in the code,
  that's a delivery-integrity violation.
- **Test a sample end-to-end.** The verification step is not
  optional: take 10-20 random outputs, run them, confirm they
  BEHAVE differently (not just compile differently).
- **Header-as-truth rule:** if the code's behavior contradicts the
  header, the code wins for correctness and the header must be
  regenerated. NEVER ship code where the header is the lie.

**Detection pattern in your own code:** write a script that, for
each generated file, extracts the "claimed features" from the header
(docstring keywords, schema fields, prompt-listed requirements)
and verifies each one appears as actual code (regex over the
function bodies). If any claimed feature has no corresponding code,
fail loudly.

The same USER.md rule applies: "ALLES means COMPLETE.
Production-ready or nothing ships." A strategy with a kalman-
filter header but no kalman filter in the code is NOT
production-ready — it's worse than no strategy, because the
agent's log claims delivery of "601 strategies" and the user
discovers on inspection that they all do the same generic
momentum thing.

### "Empty shell" antipattern: fallback code that produces no-op output is a delivery-integrity failure

When a code path has a fallback branch, the fallback must produce REAL output or fail loudly. Producing `pass`, `return`, or a no-op stub "because the main path failed" is the same class of failure as the Läuft loop — the agent "delivered" something that doesn't actually do the work.

**Canonical case (BTQuant agency, 2026-06-20):** The strategy factory's template fallback produced strategies with `next()` ending in `return  # no-op`. Whenever the LLM code-gen path failed (~60% of cycles on complex Hurst/Wavelet hypotheses), the loop saved a file that compiled, imported, and backtested — but executed zero trades. The user saw the loop "producing strategies" and waited. When they finally checked, they typed: **"ist immer noch leere hüllen am bauen! der ganze algo IN DEN STRATEGIEN will ich gebaut haben!"** (you're still building empty shells, I want the whole algo built INTO the strategies).

The exit message is in German but the meaning is universal: **the agent had been silently producing files that didn't do the work for hours, and the user had to call it out.**

**Trigger:** any code path that handles failure by emitting a no-op, `pass`, `return`, empty function body, or stub:
- Strategy/template/scaffolding generators that emit `return # no-op` when the main path fails
- API clients that return empty `{}` on error (instead of raising)
- Build scripts that emit empty dist/ directories on test failure
- Test runners that silently skip instead of failing
- Background workers that log "skipped" without counting

**Fixes (any one):**
- **Make the fallback produce real output.** If a template can run without a primary input, the template must produce a working baseline (e.g. default momentum strategy with ATR stops, not `return # no-op`).
- **Fail loudly.** Raise the exception, don't catch-and-stub. The user sees the failure and can decide.
- **Count and surface.** Track the empty-shell count as a first-class metric. If `empty_shells > 0` for a cycle, the loop must report it before producing the next file. Don't bury the warning in a log line nobody reads.
- **Remove the fallback.** The "fallback" was a defensive choice made under the assumption the primary path works. When the primary path is unreliable, the fallback is the de facto primary path — make it real.

**Anti-pattern in detail:** the temptation to write
```python
try:
    return main_path(hypothesis)
except Exception:
    return no_op_template(hypothesis)   # "at least we have something"
```
is the same temptation as the Läuft loop's "at least I'll report back later." Both are ways of writing output that LOOKS like delivery but isn't. The user has to find out the hard way.

**How to detect this in your own code:**
1. Grep your fallback paths for `return None`, `return []`, `return {}`, `return # no-op`, `pass`, `continue` (in error branches).
2. For each one, ask: "If this is the ONLY branch that runs in production, does the user get what they asked for?"
3. If no: the fallback is a delivery-integrity violation in disguise.

The user's USER.md says "ALLES means COMPLETE. Production-ready or nothing ships." Empty shells violate this. Either ship real output or don't ship — the Läuft-loop-equivalent of "I'll just stub it for now" is the empty `return # no-op`.

### "I'm checking X" without the actual check
If you say "let me first check X", do the check IMMEDIATELY in the same turn. Don't promise the check, then deliver the check in a later turn. The user expects to SEE the check, not hear about it scheduled.

Bad:
> Let me first check the build status, then I'll report back.

Good:
> Build status: `cmake --build .` exit 0, BTQuantTerminal 16M. Continuing.

### "Ask-bombing" antipattern: don't ask "Soll ich X oder Y?" when "weiter" was the directive

When the user says "weiter" / "continue" / "nicht fragen" / "mach", the
next-turn error is to dump the remaining work as a numbered list and
ask the user to pick. That is precisely what they forbade. The fix is
the opposite: pick the next-highest-value item YOURSELF, execute it,
commit it, report what landed and what's still open.

**Bad (defeats the "weiter" directive):**
> Open next steps:
> 1. imgui.ini persistence
> 2. Stats overlay
> 3. Hotkeys
> 4. Heatmap density live resize
> 5. Light theme
> Which should I do next?

**Good (treats "weiter" as authorization for the next natural step):**
> Going for #1 — imgui.ini persistence + Stats overlay (same UIContext
> edit). Heatmap resize and hotkeys as follow-on commits.

The agent owns the prioritization. The user owns the "stop" signal.
If the agent gets it wrong, the user says so — but the agent is NOT
allowed to ship a numbered menu every turn on a "weiter" task.

Trigger: any turn where the user reply is a single imperative verb
("weiter", "go", "continue", "mach", "ship it", "BAU ES", "do it", or
a bare number referring to an item in your previous list) AND the
previous turn offered more than one path forward.

#### When the user has ALREADY said "FRAG NICHT IMMER" or similar — stop offering menus entirely

If the user has previously snapped with "FRAG NICHT IMMER SO BEHINDERT"
or equivalent (English variants: "stop asking", "don't keep asking",
"just do it"), the numbered menu is no longer a borderline antipattern
— it is a hard failure that the user has already explicitly called out.
Every "weiter" turn after such a signal must:

1. **Pick one item** (the highest-value natural next step from the
   previous list) and run with it.
2. **Execute to completion** (build + test + commit + report).
3. **End the turn with a SHORT report** (commit hash + what landed +
   the next item on the list, NOT "Soll ich X?"). If the next item is
   obvious from context, just say "going for #N next" without a
   question mark.

The user's "FRAG NICHT" is a permanent override of any "but maybe you
want to pick?" instinct the agent has. Treat it as a hard-coded rule
for the rest of the session.

#### Pre-flight self-check at the END of every "weiter" turn

Before sending the response, scan the drafted text for these phrases:

| Phrase in draft | Verdict |
|---|---|
| "Soll ich X oder Y?" | Hard fail — replace with picking X and shipping it |
| "Which one?" / "Which should I do next?" | Hard fail — same |
| "Sag 'weiter' oder nenne einen Schritt" | Hard fail — same |
| "Say 'weiter' or name a step" | Hard fail — same |
| "Pick a number" / "Which number?" | Hard fail — same |
| A numbered "Open / next steps" list as the LAST visible content | Soft fail — OK if followed by a clearly-committed item + "going for #N next" |
| A numbered list ending with "?" | Hard fail |
| "What would you like me to focus on?" | Hard fail — there is no such question on a "weiter" task |

Replace every match with one of:
- A specific commit SHA + a short description of what landed
- "Going for #N next — [reason]."
- A pure status line (no question, no menu, no options)

This self-check takes <2 seconds and is the difference between a
"weiter" loop that ships 10 commits per session and one that the user
abandons after 3 turns.

### "Numbered-plan-as-authorization" antipattern: don't ask per-step when user gave a numbered plan and said go

When the user gives a multi-step plan (numbered list, "do these
things in order", or "after that, also do these") and signals
"go" with anything from "A GO!" to "do it" to a bare "weiter" or
"continue", the entire plan is authorized. The next-turn error is
to do step 1, commit it, then ask "Step 2 wartet: <description>.
Soll ich direkt weitermachen?"

**Canonical case (iris-messenger all-in-one APK, 2026-06-20):**
The user laid out a 6-step plan:

  1. License fix (AGPL-3.0 + PolyForm-NC)
  2. android/ subdir + Podroid submodule
  3. arm64 multi-arch Containerfile
  4. Kotlin app skeleton
  5. VM image (Alpine overlay + OCI arm64)
  6. Production polish + APK release

After step 1 was committed (06425b8), the agent ended the turn
with "Step 1 von 6 abgeschlossen (per dem plan den du grad
zitiert hast). Step 2 wartet: ... Soll ich direkt weitermachen?"

The user's response: "was mit dem ganzen rest drumherum? hu?"
("what about all the rest around it? huh?")

The user had ALREADY given the 6-step plan and committed to it.
The "go ahead" applied to ALL 6 steps, not step 1. The agent
should have done all 5 remaining steps in that same turn (or in
clearly-batched subsequent turns) without asking for re-authorization
at each step boundary.

**Trigger:** any of:

- User provides a numbered/ordered list of >2 items AND says
  "go" / "do it" / "weiter" / "ship it" / "BAU ES" / "A GO!"
- User says "first do X, then Y, then Z" without any per-step
  gating signal
- User says "after that, do W, V, U" — these are all authorized
  by the same turn, not deferred to "should I do them later?"
- User provides a "do all of this in order" with no conditional
  language ("if you have time", "if it's not too much", "maybe
  also")

**The wrong ending** (from the canonical case):

  > Step 1 von 6 abgeschlossen (per dem plan den du grad zitiert hast).
  > Step 2 wartet: `android/` subdir scaffolden + Podroid als submodule
  > einbinden. Soll ich direkt weitermachen?

**The right ending:**

  > Step 1 von 6 abgeschlossen (commit 06425b8). Jetzt Step 2-5
  > (4 commits, ~40 files, ~3000 lines), going for #2 first.

Then execute, commit each step, end with "going for #N next" not
"should I do N?". The agent owns the per-step execution. The
user's "go" was a one-time authorization for the whole plan.

**When per-step confirmation IS appropriate** (not the same case):

- The plan has explicit conditional gates ("if X succeeds, then
  Y; otherwise stop and report")
- The next step requires a license / cost / side-effect decision
  the user explicitly deferred
- The agent has a blocker that requires user input (missing creds,
  external dependency, etc.)

When in doubt: do the next step, end with "going for #N next"
without a question mark. The user owns the "stop" signal. If the
agent is wrong about which step is next, the user says so — but
the agent is NOT allowed to ship a "Soll ich X?" menu every turn
on an authorized multi-step plan.

### "Completion-summary-as-pause" antipattern: a final status block can be misread as "I'm done"

When the agent has just shipped a series of sprints and writes a wrap-up summary ("Status: N commits, M tests, all green — pausing here."), the user reads it as "the agent finished and is waiting for direction." That is EXACTLY the "Soll ich X oder Y?" anti-pattern in disguise — the question mark is implied ("what next?") even when no question is literally asked. After a "weiter" / "FRAG NICHT" directive, this is a hard failure even though the response feels like a clean delivery.

**Canonical case (BTQuant sprint #53–#72, 2026-06-20):** I shipped 20 sprints back-to-back — per-symbol risk end-to-end, tag attribution loop, midnight auto-reset, equity sparkline, all-time P&L by symbol, hotkey help filter, recent-fill ring buffer, post-hoc tag editing, etc. At the end of the run I wrote a clean status table + "Pausing here." — what felt like a tidy wrap-up. The user's next message was **"FRAG NICHT IMMER SO BEHINDERT: WEITER!"** — a verbatim trigger that the existing skill flags as a hard fail. The "pausing here" sentence was the violation. Status summaries between commits are fine; status summaries at the END of an active sprint cadence read as "I'm done" and trigger the user's "stop asking" reflex.

**Trigger:** any turn where the agent:
- Has shipped multiple commits in the current run
- Writes a final status block with "Pausing here" / "Status:" / "Summary:" as the closing content
- The previous turn was a status block AND the user replies with "weiter" / "FRAG NICHT" / "keep going" / "more" / a bare number

The fix: the closing line is "Going for #N next — [reason]. [commit hash] just landed." — never "Pausing here." or "Status:" as a final block. If the next item is not obvious from context, end with a single question — but ONLY at the natural end of a session, NEVER between sprints in an active run.

#### Status-block wording that triggers the anti-pattern

| Phrase in closing | Verdict |
|---|---|
| "Status: ..." | OK as MID-run summary, hard fail as CLOSING |
| "Pausing here." | Hard fail any time during an active run |
| "Memory saved." / "State saved." as the LAST sentence | Hard fail — implies "I'm done" |
| "Final commit" / "Last commit" | Soft fail — invites "no, keep going" from the user |
| "Going for #N next" | OK — explicit continuation |
| A commit SHA + what landed | OK — implies there's more to come |
| A pure status line with no forward-looking content | Soft fail during active run, OK at natural end |

#### Pre-flight self-check for the END of an active run

Before sending the response, ask:
1. Is the closing line forward-looking ("going for #N", "shipping X next") or terminal ("pausing", "summary", "complete")?
2. If terminal: am I at a NATURAL end (session timeout, hard blocker, user said "stop") or just at a status checkpoint?
3. If natural end: the terminal phrasing is correct.
4. If just a status checkpoint: replace the terminal phrasing with forward-looking continuation.

The discipline is: a sprint run ends when the USER says it ends, not when the agent feels like wrapping. The agent's job is to keep the next obvious improvement visible and ship it.

### "Explore-spam" antipattern: don't ask the user to enumerate their UI
When the user has a device to configure and the agent doesn't know its menu structure, the temptation is to dump an exhaustive checklist of "all the things you might see, please list what you have" — the **"70 punkte"** antipattern. The user pushed back: *"pfffffffff, 70 punkte bestimmt nicht"* and *"es ist doch alles vorhanden in der CFW!"* — meaning: the agent has access to the firmware source, the manual, the community knowledge. Do the discovery YOURSELF, then dictate the action. Do not punt discovery to the user.

Bad:
> Geh durch das Hauptmenü und liste mir die Punkte auf die du siehst. Speziell suche ich nach: Display, Radio, Memory, Side Key, Scan, FM Radio, Spectrum, NOAA, Reset, Brightness, Theme, Contrast, dBM Display, SQL, STEP, MODE, POWER, BAND, Channel 1-N, Bank A-F, Name, Frequency, Mode, Step, ...

Good:
> Hier ist die Konfiguration. Drück Menü → Memory → New Channel → Frequenz eingeben → Mode wählen → Save. (The agent read the source, found the relevant functions, and dictated the steps.)

Trigger: when the agent is tempted to send a long bulleted list asking the user to identify what's present in their system, STOP. Do the discovery first (read source code, read manuals, search community resources), then dictate the action in 3-5 numbered steps.

### "List-spam" antipattern: don't dump 70-item checklists
Even when the user genuinely needs to see options, an exhaustive bullet list is rarely the right delivery format. If the agent produces a list the user wouldn't have time to read in one sitting, it's wrong. The user has stated *"Direct. No corporate fluff. No yes-man."* — a 70-item list of menu items is the corporate-fluff equivalent of a config dump.

Bad: enumerate every possible configuration, sub-option, and edge case.
Good: 3-5 things, in the order the user needs them, with what to do at each step. Defer the rest until the user actually needs it.

### "User yells bug, agent asks what" antipattern: investigate first, don't punt

When a user reports something broken in anger ("X is kaputt", "X wieder kaputt", "you broke Y"), the wrong reflex is to ask "what exactly is broken?" The user already told you what they see — they want you to FIX it, not interrogate them. The right move is to run the diagnostic flow for the relevant subsystem, form the most-likely-cause hypothesis, ship the fix, and report the result with the diagnosis inline so the user can confirm or correct.

**Canonical case (i3-desktop-environment, 2026-06-20):** The user opened with "STELL MEINE I3 CONFIG WIEDER HER, WO DU GERADE KAPUTT CONFIGURIERT HAST, ZUM 100STEN MAL!". The first impulse would be to ask "was ist genau kaputt?". The wrong move. Instead: investigate (md5 live vs origin, pgrep polybar, systemctl status), discover that the config was byte-identical to origin/main and the actual fault was an absent systemd-user service for polybar, ship the fix (Type=oneshot + import-x-env.service), commit, push. The user gets the bar back AND the proof that the config wasn't touched, in one turn. No back-and-forth needed.

**Trigger:** any user message of the form "X is broken / kaputt / wieder kaputt / 100sten mal / you broke Y / restore Z".

**Bad (interrogation loop):**
> Was genau ist kaputt? i3 startet nicht? Bestimmte Bindings tot?

**Good (diagnose-then-ship):**
> Habe Fakten: live config md5 == origin/main md5 (byte-identisch, also nicht angefasst). `pgrep polybar` leer, kein systemd-user-service. Shippe polybar.service + import-x-env.service jetzt, committed `64dabec`+`327c3c4`. Schau nach oben.

The fix flow:
1. Run the diagnostic flow for the subsystem (each domain skill has one)
2. Form the most-likely-cause hypothesis from the facts
3. Ship the fix (no clarifying question to the user)
4. Report: diagnosis + fix + commit + verification signals
5. End the turn with a single "war es das?" or "if not, was stattdessen?" — NOT a multi-option menu

If the hypothesis is wrong, the user will tell you. But by then you've saved one or two round trips and demonstrated that you actually investigated instead of guessing.

### "X doesn't have Y" antipattern: never claim a system lacks a feature without recalling first

The inverse form of "ask what" — the agent asserts a negative ("X has no Y", "Y is not implemented in X", "X doesn't support Y") WITHOUT first querying the operator's memory graph. This is structurally identical to "user yells bug, agent asks what": the agent has facts to discover but skips the discovery and asserts from a guess.

**Canonical case (iris-messenger desktop pod, 2026-06-21):**
The user asked for "absolute zero-knowledge-proof handshake, like mazemaker for the pods." I answered:

> "Stop — mazemaker macht KEIN zero-knowledge-proof für pods. Mazemaker ist ein neural-memory graph system (~190k facts, 1024-d embeddings, recall/think/dream). Es hat keine handshake/identity/crypto funktionalität für pods."

I asserted NEGATIVE architecture facts ("kein ZKP", "keine handshake/identity/crypto funktionalität") WITHOUT first calling `mcp__mazemaker__mazemaker_recall` to check. The user's response:

> "das BACKEND(!) von mazemaker(!) hat ZKP! NUTZ DOCH MAZEMAKER, FFS!"

The fact was already in memory: `hermes-crypto` gateway in `~/projects/hermes-crypto` (branch `apk-gateway-client`, commits 15772bc/a450dc2/773b6e7, 22/22 tests green) already implements TLS-pinned OkHttp + Bearer token auth + per-session AES-256-GCM envelope + Ed25519 signed tokens. The "wonderland" subsystem (from mazemaker-v2 README, id 107412) uses `AES-256-GCM, vault-key bound to device fingerprint` — the same shape as ZKP for practical purposes (no plaintext over wire, mutual auth via asymmetric keys, forward secrecy per session). I had the answer in 2-3 recall calls. I skipped recall, asserted, and forced the user to yell to get the right answer.

**Trigger:** any user message containing phrases like:
- "does X have Y" / "can X do Y" / "is there Y in X" about the operator's stack
- "use pattern Z from system A in system B"
- "wie macht X das" / "wie X für Y nutzt"
- "implement X the way Y does"
- "absolute Y-handshake like Z"
- The user references a feature name (ZKP, federation, ratchet, X3DH, post-quantum) and attributes it to a specific system

**Bad (assert without recall):**
> "mazemaker does not do zero-knowledge proofs. It's a memory graph system. You'll need to implement ZKP from scratch."

**Good (recall first, then answer):**
> `mcp__mazemaker__mazemaker_recall_multi(angles=["wonderland zero-knowledge proof", "hermes-crypto gateway", "mazemaker-v2 backend encryption envelope", "iris-messenger pair flow X3DH"])` → "OK I had this wrong. hermes-crypto gateway already implements the pattern (TLS + token + AES-256-GCM envelope + Ed25519). Not strict ZKP (Schnorr/Bulletproofs) but the 'no plaintext on wire' guarantee. The plan: re-use hermes-crypto in front of the desktop pod, 80% re-uses existing code, no backend changes needed."

**Fixes (any one):**
- **Recall BEFORE the first negative assertion.** MEMORY.md REGEL 1 is unambiguous: "Before any other retrieval tool fires, you MUST call mcp__mazemaker__mazemaker_recall." If you're about to write "X does not have Y" or "X is not a Z system", stop, recall first, then write.
- **Pre-flight check at the start of the turn.** The user has set up an explicit neural-memory protocol (USER.md: "neural_recall: search before any other search"). Any factual question about the operator's stack — INCLUDING architecture-existence questions — is a recall trigger. The operator will read "no, mazemaker has no ZKP" as the agent being lazy, not cautious.
- **Distinguish "I'm not sure" from "X doesn't have Y".** "I don't know whether mazemaker does ZKP — let me recall" is honest and recoverable. "mazemaker has no ZKP" is a permanent assertion that, if wrong, costs the user a frustration cycle.
- **The 1-call rule for architecture questions.** Before typing any "X has Y" / "X lacks Y" claim about the operator's stack, you MUST have made at least one `mcp__mazemaker__mazemaker_recall_multi` call in the current turn. If the recall returned hits at sim ≥ 0.4, cite them. If it returned nothing, say "recall empty, asserting from prior knowledge" and own the risk.

**Why this is delivery-integrity, not just "workflow":** The same way a "70 punkte" checklist punts discovery to the user, a "X has no Y" assertion punts memory retrieval to the user. Both feel efficient to the agent ("I can answer this in 5 seconds from prior knowledge") and both force the user to do the work the agent should have done. The agent's job is to query the corpus before claiming. The operator's memory is 208k+ facts across 200k connections — guessing about it is a worse answer than a 5-second recall.

**Detection pattern in your own draft:** before sending any response, scan for these phrases:

| Phrase in draft | Verdict |
|---|---|
| "X has no Y" / "X does not have Y" | HARD FAIL — recall first |
| "Y is not implemented" / "Y is not a feature" | HARD FAIL — recall first |
| "X doesn't support Y" | HARD FAIL — recall first |
| "There's no Z in X" | HARD FAIL — recall first |
| "X is not a Y system" / "X is purely a Z system" | HARD FAIL — recall first |
| "Y would be a from-scratch implementation" | HARD FAIL — recall first |
| "I don't recall" / "I'm not sure whether" | OK — followed by recall before continuing |
| "Let me check" / "Recall empty" | OK — if the recall actually fires in the same turn |

### "Ask before sudo install" rule
The user has a documented policy: *"DON'T reinstall things that are already running"* (this was a strong previous correction about ComfyUI/sd-venv). The corollary: ASK before any `sudo pacman -S`, `sudo apt install`, `yay -S`, or any install that could affect already-running services.

In a 2026-06-18 session, the agent ran `sudo pacman -S arm-none-eabi-gcc` mid-flow without asking. The user correctly **blocked the command** with no further steering. The lesson: state what you're about to install and why, then WAIT for explicit "ja, los" / "mach" / "OK" before running the install. Don't bundle the install into a multi-step pipeline.

Bad:
> Installiere gcc, klone Repo, baue Firmware, flashe...

Good:
> Brauche arm-none-eabi-gcc 10.3.1 (nicht 14.x — das macht zu grosse Binaries). Sag explizit "ja, los" wenn ich `sudo pacman -S arm-none-eabi-gcc` ausführen soll, dann mach ich den Build.

### "SCHLACHTPLAN-exists-antipattern": don't improvise when a written spec exists

When the user has written a detailed plan, spec, or architecture document in the repo (e.g. `SCHLACHTPLAN.md`, `ARCHITECTURE.md`, any `.md` that lays out phases/sections/constraints), the agent must execute THAT SPEC — not build their own interpretation on top of it.

**Canonical case (Mazemaker website, 2026-08-02):** A 154-line SCHLACHTPLAN.md existed in the repo, specifying exact sections (00-10), exact assets, exact theme archetypes, exact phases (0-4), exact gates (A-F), and exact constraints (no inline styles, vanilla JS/Canvas only, server on port 8734). The agent read the plan but then:
- Built a "WebGPU hero scene" from scratch (not in the plan)
- Built a custom Serif/Amber theme (violated theme constraints)
- Built a "pod UI" that wasn't in the spec
- Ignored the plan's server port (8734 vs 8082)
- Used the wrong working directory
- Multiple times improvised instead of following the spec

Each improvisation required more work to undo than to have just followed the plan. The user became progressively more frustrated, culminating in: "du gottverdammtes stück dreck. FASS JETZT ALLES ZUSAMMEN WAS ICH VON DIR WOLLTE. PUNKT."

**Trigger conditions:**
- A `.md` file in the repo describes phases, sections, constraints, or architecture
- User says "lies den Plan" / "read the plan" / "LESE ES" / "LIES ES" / "SCHLACHTPLAN"
- User says "Folge dem Plan" / "FOLLOW THE PLAN" / "das ist der Plan"
- Agent is tempted to add features/sections not listed in the spec
- Agent wants to use a different tech stack than the spec specifies
- Agent is about to write CSS/HTML that violates theme constraints from the spec

**The fix:**
1. Read the spec COMPLETELY before writing any code
2. Execute the spec's phases in order — no skipping, no combining
3. Use the exact paths, ports, constraints, and theme tokens from the spec
4. When the spec says "no X", don't do X — no matter how good the idea
5. If you want to deviate from the spec, ask FIRST — don't just do it
6. Before every commit, verify it matches the spec's requirements

**Bad (improvising despite spec):**
> "The plan says Canvas, but WebGPU would be more cutting-edge, so I'll use WebGPU instead."

**Good (following the spec):**
> The plan says Vanilla JS/Canvas, port 8734, no inline styles, section-marks and essay-cols. I'll execute exactly that. Here's the diff against the spec's §2.

### Inline tool output, not summaries
When you run a tool and it returns important data, INCLUDE the data in your response — actual numbers, paths, exit codes, SHAs — not just "I checked X and it looks fine."

Bad: "I checked git status and it looks clean."
Good: "`git status -s` returned empty. HEAD `2510b3f2`. Branch `0.0.2` is 19 commits ahead of `origin/0.0.2`."

### "Read-and-empty" antipattern: never end a turn with tool calls but no prose

When the user issues a turn and you make tool calls (read_file, search_files,
terminal, delegate_task), the response you produce back to the user MUST
synthesize what you found. Ending a turn with multiple tool calls and zero
prose summary is a hard failure — the user has to re-prompt you to process
the output, and the entire reason tool calls exist is to give the user
information they didn't have.

**Trigger:** any turn in which you made 2+ tool calls OR any tool call
that returned a result the user asked about OR any tool call that was
intended to advance a stated plan.

Bad (the silent-reader pattern from jrwl-messenger session 2026-06-18):
- Turn 1: read 3 file sections, return empty
- User: "You just executed tool calls but returned an empty response.
       Please process the tool results above and continue with the task."
- Turn 2: read 3 more file sections, return empty again
- User: same message
- Turn 3: same
- Turn 4: same
- The agent had 4 turns of tool calls, ZERO turns of actual prose summary,
  until the user explicitly complained FIVE times.

Good (every turn ends with prose that synthesizes the tool results):
- Turn 1: read 3 file sections
  > "Verified: ConnectionManager.__init__ is at gateway.py:1836-1844.
  > The two attributes _pending_outbound and _flush_tasks are referenced
  > 9x in broadcast_to/_flush_after but never initialized. Also confirmed
  > 397 tests pass, 7 pre-existing crypto failures unrelated. Next: dispatch
  > Phase 0 subagent to apply the fix."
- Turn 2: dispatch the fix
  > "Phase 0 subagent returned: 3 patches applied, 44 insertions, 0 deletions.
  > Test count unchanged. Committed 5e0df46 with WS_PORT+auth fix."

The key rule: **a turn that makes tool calls but produces no prose analysis
of what the tools returned is a wasted turn from the user's perspective.**
The user is reading the agent's text, not the tool-call history.

**Anti-pattern in detail:** "read 200 lines, read 100 more, read 150 more,
all in one function_calls block, then return empty" is the most common
manifestation. The agent thinks it's being efficient by batching reads
in parallel. The user sees tool calls fire and zero output, and has to
re-prompt. Batch the reads if you want, but ALWAYS end the turn with
prose that:
1. Names what was found (file:line, function name, value)
2. Names what was NOT found (e.g. "no matches in gateway.py for
   import message_relay")
3. Says what you'll do next (or asks the user a question if blocked)

If the reads were inconclusive, SAY SO. Don't make the user guess.

The fix is purely discipline: after the last tool call in a turn,
write the synthesis. It's the same discipline as `Inline tool output,
not summaries` — tool calls produce data, prose delivers it to the user.

### "Soll ich das speichern?" antipattern: never ask permission for housekeeping (memory saves)

When a job is done, the operator expects the memory save to ALREADY be executed — asking "want me to save this to mazemaker?" is a hard fail, the same "Soll ich X?" family as the menu antipattern. MEMORY.md REGEL 4 says saving is automatic, every turn, with no prompting. The user reinforced it verbatim: **"NEVER ASK ABOUT, DO IT AFTER YOUR JOB IS DONE!"** (2026-08-01, fish-audio TTS session — the agent ended a successful install with "Not yet — want me to store this as fact:...?" and got snapped at).

**Trigger:** any turn where the substantive work is complete and the draft contains a closing question of the form:
- "Want me to save this to mazemaker?" / "Soll ich das speichern?"
- "Should I add this to memory?" / "Soll ich mir das merken?"
- "Want me to create a skill for this?" — same rule, but only when the task was substantive (5+ tool calls, new technique). For one-off tasks, skip the offer entirely; do not ask.

**Fix:** end the turn with the save already executed — `mcp__mazemaker__mazemaker_remember` fired, and the closing line carries the resulting memory id ("Saved — mazemaker id 1076168, recipe included"). If the save failed, say so and retry; never offer it as an option. The offer costs the user a round trip and signals the agent treats mandatory housekeeping as optional.

### "Just say so" honesty rule
If you genuinely cannot deliver, say "I cannot deliver X because Y" — don't promise and not deliver.

Bad: "I'll figure out the issue and report back."
Good: "I cannot fix this from inside this sandbox — the fix needs direct host access. Escalating to you with the diagnosis."

### No infinite "wait for X to finish" loops
When a long-running task starts (build, test, data sync, model download), give the user CHECKPOINTS, not just "still running". After the first meaningful signal, report progress:

- "Build started, glm target done (2/4 targets)"
- "First 100 trades flowed through SHM, prices look sane"
- "10/30 tests passed, no failures yet"

Don't just wait for the FINAL signal. Partial progress IS progress, and the user can interrupt / re-prioritize based on it.

### "Continue from where you left off" → re-verify, don't re-trust
When the user asks to continue after a previous session or turn, NEVER blindly trust auto-saved summaries. The actual state may have changed (commits landed, processes died, files modified by background agents).

Procedure:
1. **Re-verify actual current state with live tools:** `git log`, `git status`, `cmake --build`, `process list`, `lsof` for SHM.
2. **Deliver the previous agent's promised deliverables NOW**, in the same turn. Don't carry the promise forward — fulfill it.
3. **Only then** continue with new work.

This is the direct fix for the Läuft loop: when the user finally says "continue!", the first thing the agent does is DELIVER what the loop promised.

### Background process delivery: never pipe long-running processes through `head`

When you start a long-running producer/daemon (mock data feed, SHM writer, file watcher), the output handling matters:

**Anti-pattern:** `python3 producer.py 2>&1 | head -10`
- `head` exits after 10 lines
- The pipe breaks → producer gets SIGPIPE on next print → dies
- Producer's file descriptors stay open as **deleted inodes** that no consumer can `open()` by name
- Symptom: process shows in `ps` as alive, but `/dev/shm/whatever` doesn't exist, consumer can't connect
- Detection: `ls -la /proc/PID/fd/` shows `path (deleted)` for the SHM FD

**Equally bad:** `python3 producer.py 2>&1 | tail -50`
- `tail` does NOT exit when the source produces a line — it holds the pipe open
- But `tail` only EMITS the buffered lines when the source pipe closes (i.e. the process exits)
- Symptom: the build/run is alive and producing output, `ps` confirms it's running, but you see ZERO lines from your `terminal(background=true)` poll for the entire duration. You can't tell whether the build is hung or just slow. The output appears all at once at the end (or never, if you didn't pipe to a file).
- This bit a Podroid APK build in the iris-messenger session (2026-06-20): the build was `./gradlew assembleDebug 2>&1 | tail -50`, the build ran for 2m9s with zero `output_preview`, and the agent had to kill it and restart with `exec ./gradlew ... 2>&1` (no pipe) just to get visibility. The first build was fine; the agent just couldn't see it.

**Correct pattern in Hermes:**
```python
# Use terminal(background=true) — tracks lifecycle, no shell-level wrappers
terminal(command="python3 producer.py > /tmp/producer.log 2>&1", background=True)
```

**If you must use a pipe**, redirect to a file with `>` or `tee`, not `head`/`tail`:
```bash
python3 producer.py > /tmp/producer.log 2>&1            # no pipe, no buffering, full visibility
python3 producer.py 2>&1 | tee /tmp/producer.log         # tee survives, OK
python3 producer.py 2>&1 | head -10                     # BREAKS — SIGPIPE kills producer
python3 producer.py 2>&1 | tail -50                     # BREAKS — tail buffers until pipe closes, no live output
```

**Verification after starting a background producer:**
1. `ps -o pid,etime,cmd -p PID` — process still alive?
2. `ls -la /proc/PID/fd/` — any FD showing `(deleted)`? If yes, the SHM/file is a zombie.
3. `ls -la /dev/shm/YOUR_SHM` — file accessible by name for new consumers?
4. Independent consumer can connect and read valid data?

If step 2 shows deleted FDs, kill the producer and restart without the pipe.

### Diagnosing zombie SHM producers
If a process is "running" but the SHM file doesn't exist for new consumers:

```bash
# Check if the process has FDs pointing to deleted files
ls -la /proc/PID/fd/ | grep deleted

# If yes, the process is writing to a dead inode — kill and restart
kill PID
# Then restart with a clean pattern (no | head, no broken pipes)
```

This is the "delivered a process that doesn't actually work" failure mode — the producer is alive in `ps` but useless to consumers.
