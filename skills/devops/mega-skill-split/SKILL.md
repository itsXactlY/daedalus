---
name: mega-skill-split
description: Split oversized SKILL.md files (>40KB) into a lean core + references/*.md while keeping the router catalog intact. Trigger when a skill_view loads 20k+ tokens, when SKILL.md bodies exceed ~40KB, or when user asks to slim down mega-skills (e.g. "Wave 2 skills audit"). Complements daedalus-skills-cleanup (which only removes whole skill dirs — this edits content). Frontmatter name/description must stay verbatim so the auto-router keeps matching.
---

# Mega-Skill Split — lean SKILL.md core + references/

Used 2026-08-12: 15 skills split (100KB → 7KB worst case). Proven workflow
with a hard-won range-bug lesson. Wave-3 candidates (dense cores, 29-39KB,
never >40KB): mazemaker-dream-pipeline 39, jrwl-messenger-crypto-audit 37,
humanizer 36, ml-paper-writing 34, prompt-injection-defense 33,
i3-desktop-environment 29.

## Golden rule: frontmatter is sacred

The auto-router (`agent/skill_router.py`) matches on `name` + `description`
from the catalog (`load_skill_catalog()` → entries have key `skill_name`,
NOT `name`). Keep frontmatter name/description 1:1 verbatim — routing stays
identical. Only the body changes.

## Split decision

- Hand-crafted splits for CHRONOLOGICAL/EPISODIC logs (dated entries,
  learning logs, bug chronologies): move dated subsections wholesale into
  references/*.md (e.g. `references/learnings-01.md`..`04.md`, chunked by
  theme). Best result: pulse-wurm2-tick-learnings 100→7KB (44 learnings →
  4 ref files), tri-state-decision-process 98→13KB (51 pitfalls →
  references/pitfalls-full.md).
- Generic threshold splits for SECTION-BASED content: for each H2 section
  >= ~4KB, move the whole section (from its `## ` heading to the NEXT
  heading — see range bug!) into one `references/moved-sections.md` per
  skill. Keep the original `## ` heading as a stub with a pointer line:
  `Detailed steps: see references/moved-sections.md`.

## Keep-inline rules (hard rules stay in SKILL.md)

Sections that MUST remain inline: `## Trigger`/trigger block, hard rules /
`CRITICAL` / MUST / invariant statements, quick pitfalls list, references
pointer section, core workflow (first 3-5 steps), setup/verification
commands. Move: deep dives, full examples, extended troubleshooting,
historical context, verbose pattern catalogues.

## THE RANGE BUG (cost 5 skills, 1-4KB castration)

When moving H2 sections, a naive splitter computed each moved section's
range as `start_of_moved .. start_of_NEXT_MOVED` — swallowing every small
keep-section in between. Result: dayz-integrations 1KB, codebase-due-diligence
2KB, marketing-website 1KB, phone-as-pod 4KB, maze-crew 4KB.

- CORRECT: section end = line of the NEXT `## ` heading (any heading, moved
  or kept), NOT the next moved heading.
- DETECTION: after the split, count H2s in `references/moved-sections.md`
  and compare against the planned count (43 actual vs 11 planned = red
  flag). Also sanity-check final SKILL.md size: 1-4KB from a 40-74KB
  original is ALWAYS wrong.
- RECOVERY: `git checkout -- <original files>` (10 originals were in git),
  re-run corrected splitter. Commit originals first if not yet committed!

## Steps

1. `cd ~/.hermes` — relative skill paths fail from other dirs.
2. Inventory: walk `skills/`, regex `^---\s*\n(.*?)\n---` for frontmatter,
   `^name:\s*(.+)$` for name, `os.path.getsize` for SKILL.md size. List
   skills >40KB.
3. Per skill: list H2 sections with line + size
   (`re.match(r'^## ', line)` over lines). Choose hand-crafted vs generic
   per the decision above.
4. Write `references/moved-sections.md` (or themed refs) with moved
   content; replace moved sections in SKILL.md with heading stub + pointer
   `skill_view(name, file_path='references/...')`.
5. VERIFY per skill: (a) moved-sections H2 count == planned count,
   (b) final SKILL.md size sane (>=5KB, <=40KB), (c) frontmatter diff empty:
   `git diff skills/X/SKILL.md | head` must show only body changes.
6. Full verification suite (measured, not claimed):
   ```bash
   cd ~/.daedalus && python3 -c "
   from agent.skill_router import load_skill_catalog, route_skills
   index = load_skill_catalog()
   names = ['<split skill names>']
   missing = [n for n in names if not any(e.get('skill_name') == n for e in index)]
   assert not missing, missing
   print('all split skills present:', len(names)-len(missing), '/', len(names))
   print('router test:', [r.get('skill_name') for r in route_skills('<domain query>', top_n=3)])
   "
   python3 -m pytest tests/skills/ tests/tools/test_skills_tool.py tests/agent/test_skill_router.py -o addopts="" -q --ignore=tests/skills/test_google_oauth_setup.py --ignore=tests/skills/test_google_workspace_api.py
   timeout 90 daedalus curator run   # expect: checked=N stale=0 archived=0
   ```
7. Commit in ~/.daedalus with per-skill before→after KB
   in the message. Wave-2 commit pattern: `refactor(skills): split N
   mega-skills — lean SKILL.md core + references/`.

## Pitfalls

- Catalog entry key is `skill_name`, not `name` — writing `e['name']` in
  verification raises KeyError.
- `ls` is aliased to eza/exa with icons → `invalid value for '--icons'`
  error. Use `[ -f "$f" ]`, `/usr/bin/ls`, or Python.
- test_google_oauth_setup.py / test_google_workspace_api.py have 9
  PRE-EXISTING errors unrelated to splits — always pass `--ignore=` for
  them; don't chase them during a split wave (verified pre-existing via
  `git stash` on clean tree).
- Curator checks ~292 skills: `checked=N stale=0 archived=0` proves the
  new references/ structures are structurally valid.
- Gateway restart (`--replace`) needed only if the running instance must
  see the changes immediately; catalog is rebuilt per-session anyway.
- Stale tests for deleted adapters (Slack/HA/Webhook/Telegram) can poison
  collection with errors — trim/remove them in the same wave and re-check
  `pytest --collect-only -q` counts.

## Verification checklist

- [ ] all split skills present in router catalog (skill_name key)
- [ ] router smoke test returns expected skills for domain query
- [ ] pytest: 162 passed (skills + skills_tool + skill_router suites)
- [ ] curator: 292 checked, 0 stale, 0 archived
- [ ] no SKILL.md < 5KB (castration detector), none > 40KB
- [ ] frontmatter name/description unchanged (git diff check)
- [ ] git commit with before→after sizes
