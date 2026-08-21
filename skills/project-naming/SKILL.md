---
name: project-naming
description: |
  Class-level skill for naming the operator's projects, modules, sub-brands,
  internal tools, and codenames. Captures the operator's naming DNA: every
  name must carry 2-4 cross-references from different reference frames
  (Alice in Wonderland, Inception, Matrix, Greek myth, Kabbalah, Arthurian
  legend, botany, crypto, sci-fi, folklore). Single-source-reference names
  trigger the operator's strongest negative signal: "alles schwachsinns
  namen!" — which means the name is rejected and the whole brainstorm is
  reset. This skill prevents that failure.
version: 1.0.0
tags: [naming, branding, alca-stack, projects, design]
triggers:
  - "rename an existing project"
  - "new project needs a name"
  - "name a module / sub-brand / internal tool"
  - "operator's project naming convention"
  - "what should we call X"
metadata:
  hermes:
    category: software-development
---

# Project Naming — Alca Stack

## WHEN TO USE

Trigger this skill whenever the operator asks for a new name, asks to
rename an existing project/module/sub-brand, OR expresses dissatisfaction
with generic naming options. The single-source-reference failure mode
("Warren = rabbit warren", "Iris = Greek goddess", "Whisper = onomatopoeia")
is loud: operator will say "alles schwachsinns namen!" and mean it. The
fix is in this skill.

## THE NAMING DNA (the operator's actual convention)

Every project name in the operator's stack carries 2-4 cross-references
that stack meaningfully. Examples (all confirmed via mazemaker):

- **Mazemaker** = Alice maze-maker + Inception "inceptions as a service"
- **JRWL** (Jackrabbit Wonderland) = Alice + cryptid folklore
- **Hermes** = Greek messenger god
- **Pulse** = heartbeat/signal metaphor for ratnest research recursion
- **Stem** = botanical (branches grow from stem) + stem-cell + verb (stem from)
- **ATRA** = acronym-as-god-name (Autonomous Trading Revenue Agent, butchery)
- **QuantRalph** = autonomous agent name (Ralph) + quantitative trading
- **Jack-in-a-Box** = toy + character reference
- **DLMkermit** = DLM framework + Kermit (Muppets)

Alice in Wonderland + Inception + Matrix = the THREE primary mindfuck
reference frames the operator draws from. The full atlas with cross-
references is at: `references/operator-naming-atlas.md`

## REFERENCE FRAMES (the operator's palette)

Pick 2-4 layers from DIFFERENT frames for each new name. Same-frame
stacking is not enough.

- **Alice in Wonderland** — wonderland, jabberwock, cheshire, madhatter,
  looking-glass, rabbithole, queen-of-hearts, madmaker, march hare,
  tweedledee/tweedledum, bandersnatch, snark, mimsy, slithy, gyre
- **Inception / Mindfuck-Layer** — dream layers, limbo, totem, kick,
  ariadne (dream architect), PASIV device
- **Matrix** — morpheus, trinity, neo, zion, construct, déjà vu,
  red pill, oracle, agent, glitch, white rabbit (overlap Alice)
- **Greek Mythology** — hermes, iris, mercury, caduceus, charon,
  ariadne, prometheus, pandora, persephone, morpheus, atropos,
  clotho, lachesis, moirae, apollo, janus, nyx
- **Kabbalah / Hebrew Theology** — hod (literally "message"), chokhmah,
  binah, tiferet, netzach, yesod, malkuth (10 Sephiroth)
- **Arthurian Legend** — pendragon, excalibur, avalon, merlin,
  morgan le fay, lancelot, galahad, perceval, camelot
- **Botany / Natural** — stem, branch, root, hollow, grove, moss,
  bramble, thicket, glen, vale, dell, meadow, copse
- **Crypto / Cryptography** — cipher, ratchet, hash, key, vault,
  conduit, sluice, drift, threshold, vestibule
- **Sci-Fi / Fandom** — patronus (HP), bandersnatch (Carroll+Apple),
  ouroboros, palimpsest, liminal
- **Folklore / Cryptids** — jackalope, jackrabbit, wendigo,
  chupacabra, mothman
- **Trickster / Cartoon / Muppets** — kermit, ralph, jack, loki,
  anansi, coyote, br'er rabbit

## STEPS (apply in this order)

### 1. RECALL THE PROJECT UNIVERSE FIRST (REGEL 1)

Call `mazemaker_recall` for the operator's existing project names
and their origin stories. Useful seed memory IDs:
- ATRA: 763680 (fact:hackathon-atra)
- Stem: 796297 (auto:turn:20260618_040912), 818340, 818348, 818349
- Pulse: 694092 (pulse skill, auto:turn:20260611)
- QuantRalph: 22814, 1340, 574748
- JRWL: 822349, 24313
- Mazemaker: 193671 (Mazemaker — Inceptions as a service)

**Fallback chain when mazemaker MCP times out or is unreachable:**
`mazemaker_recall` → `mazemaker_recall_multi` → `mazemaker_think` on
hit → `session_search` → `search_files` on `~/projects/*/README.md`.
NEVER ask the operator "what is X?" before exhausting these layers.

If still no answer: be honest that mazemaker doesn't have it — but
only after trying recall + recall_multi + think + session_search.

### 2. IDENTIFY THE NEW NAME'S DOMAIN

- What does it do? (messenger, research, trading, infra, etc.)
- What reference frames naturally fit that domain?
- Family fit check: is the operator's stack single evocative words
  (Pulse, Mazemaker, Hermes, Wonderland, Stem) or compounds
  (BTQuant, Turboquant, JRWL, QuantRalph)?

### 3. PICK PRIMARY + 2-3 LAYERS

- Choose 1 primary reference from the operator's frames
- Add 1-3 secondary layers from DIFFERENT frames
- Optional phonetic/wordplay layer (hair/hare, plague/play, etc.)
- Same-frame stacking is rejected — only cross-frame layering works

### 4. VERIFY EACH CANDIDATE

- Does it have 2+ explicit reference layers from different frames?
- Does it fit the family style (single word vs compound)?
- Is each layer reachable on a single Wikipedia page?
- Is it free of trademark collisions in the operator's known territory?
- If the candidate is single-source-reference: REJECT. Build a multi-
  layered one instead.

### 5. PRESENT WITH EXPLICIT LAYERS

- Format each candidate with its reference layers visible:
  "CANDIDATE — Layer 1: <ref> + Layer 2: <ref> + Layer 3: <ref>"
- Group by angle (rabbit heritage, mythology, crypto, etc.)
- NUMBER candidates (not letters) — see `pick-menu-design` skill
  for why letters double as ordinal picks and create ambiguity
- Hand back the floor for the operator to share their own candidates
  before any destructive action

## PITFALLS

- **Single-source-reference names**: "Warren" (rabbit warren only),
  "Iris" (Greek goddess only), "Hollow" (rabbit's hollow only) all
  get rejected with "alles schwachsinns namen!". ALWAYS layer 2+
  sources from DIFFERENT frames.
- **Generic "cool" words**: Whisper, Onyx, Lapis alone — evocative
  but lack the operator's DNA. Either skip them or layer them
  heavily with cross-references.
- **Asking the operator what their projects mean**: REGEL 1 violation.
  Use mazemaker first. Only ask if mazemaker genuinely has no data.
- **Executing destructive rebrand on ambiguous input**: "a" from a
  pick-list menu can mean "pick" OR "queue more" depending on the
  option's parenthetical. ALWAYS echo-back before destructive
  action. See `pick-menu-design` skill.
- **Names that don't fit the family style**: e.g. "TurboX-Mega-Pro"
  is too commercial; "mazemaker-mobile" follows the family style.
- **Forgetting the THREE primary mindfuck frames**: Alice + Inception
  + Matrix. Any new name should be reachable from at least one of
  these, or the operator will not see the connection.
- **Lettered candidates instead of numbered**: "Pick a, b, c" makes
  letters double as both "letter labels" and "ordinal pick indicators",
  creating ambiguity. Use NUMBERS for candidate lists.
- **Stale facts about origins**: ATRA is NOT Atropos (Greek fate) —
  it's a hackathon acronym. Pulse is NOT a heartbeat (well, it is,
  but the recursive-ratnest-research angle is the live one). ALWAYS
  recall fresh from mazemaker before naming.

## VERIFICATION

Before presenting candidates to the operator:

- [ ] Each candidate has 2+ reference layers from DIFFERENT frames
- [ ] Each layer is reachable via a single Wikipedia page
- [ ] Family style match (single evocative word OR compound X-Y)
- [ ] No trademark collisions in known territory
- [ ] Layers are EXPLICITLY visible in the presentation (not buried)
- [ ] Candidates are NUMBERED, not lettered
- [ ] Echo-back mechanism in place before any destructive move
      (see `pick-menu-design`)
- [ ] Operator's 20+ in their head has been invited (they may
      have specific candidates that beat any AI-generated list)

## RELATED

- `references/operator-naming-atlas.md` — full atlas of operator's
  project names with cross-reference layers, reference frames,
  domain availability checks, single-source failures, and live
  candidates
- `pick-menu-design` — companion skill for how to present the
  candidates to the operator without creating ambiguous pick/queue
  confusion
