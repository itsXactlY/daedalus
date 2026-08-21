---
name: daedalus-skills-cleanup
description: Safe cleanup of ~/.daedalus/skills (remove neural-memory-era skills, duplicates, superseded skills) with quarantine, manifest sync, git commit, and verification. Trigger when user says the skills folder is cluttered ("zugemüllte jauche") or asks to strip old skill generations. NOT for editing skill content — only removing whole skill dirs. For slimming oversized SKILL.md bodies (splitting mega-skills into core + references/), use the sibling skill `mega-skill-split`.
---


> Ported from `hermes-skills-cleanup` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Skills Cleanup

Safe procedure for removing skills from `~/.daedalus/skills/` without breaking
the running system. Used 2026-08-11: 345 -> 322 skills, 23 quarantined.

## Golden rule: QUARANTINE, never hard-delete

Move removed skills to `/home/alca/skills-quarantine-YYYY-MM-DD/` (OUTSIDE
the ~/.daedalus git repo, so the commit only shows the intended deletions).
Write a `MANIFEST.txt` listing every moved path + restore instructions
(`mv <path> ~/.daedalus/skills/<path>`). Git commit = second safety net.

## Steps

1. **Inventory** (script, not by hand):
   Walk `~/.daedalus/skills`, for each `SKILL.md` extract frontmatter `name:`
   (regex `^---\s*\n(.*?)\n---` then `^name:\s*(.+)$`), file count, size.
   Record total SKILL.md count BEFORE (e.g. 345).

2. **Categorize candidates**:
   - (a) Era markers: frontmatter name literally `neural-memory-*` (dead
     product line, only mazemaker lives). Scan: any skill whose frontmatter
     name/title contains `neural[-_ ]memory` → delete.
   - (b) Exact duplicates: same name, compare SKILL.md content hash.
   - (c) Superseded: sibling with `-sync` / `-crew` / current-arch name
     (e.g. mazemaker-benchmark-cleanup → -sync; parallel-code-audit →
     -crew; mazemaker-finetune-unsloth → unsloth-mazemaker-orchestrator).
   - (d) Mentions-only (skill CONTENT says "neural memory" but is generic,
     e.g. devops/debugging, pulse scripts): KEEP. Do not edit content unless
     explicitly asked — "äußerste Vorsicht" means don't touch working skills.

3. **Check live dependencies BEFORE removing**:
   - `cronjob list` — any cron with `skills:` attached? (haus-suche-discord
     cron uses that skill; keep it.)
   - Keep skills referenced by deploy scripts (jack-in-a-box: pulse-saas
     deploy-vm.sh) and skills for running infra (podman skills — containers
     run on it even if user says "don't touch", the REFERENCE stays).
   - Run `mazemaker_recall` for prior cleanup attempts/decisions (a previous
     attempt was aborted; the mess persisted because of that).

4. **Validate ALL sources exist before moving** (atomic abort):
   ```python
   missing = [t for t in to_move if not os.path.exists(os.path.join(root, t, "SKILL.md"))]
   if missing: print("MISSING (abort):", missing); raise SystemExit(1)
   ```
   This caught `self-improvement-audit-results` actually living under
   `autonomous-ai-agents/` — the abort prevented a half-done move.

5. **Move to quarantine** with shutil.move, preserving relative paths,
   write MANIFEST.txt. Verify counts: `find skills -name SKILL.md | wc -l`
   must equal before − len(to_move); quarantine count must match.

6. **Sync manifest**: `~/.daedalus/venv/bin/python ~/.daedalus/tools/skills_sync.py`
   — it AUTO-CLEANS deleted skills from `skills/.bundled_manifest`
   (`cleaned` line; `wc -l .bundled_manifest` == new skill count). Do NOT
   hand-edit the manifest.

7. **Commit** in `~/.daedalus` (the daedalus-backup repo):
   `git add -A skills/ && git commit`. Category-by-category message listing
   every removed skill and why + where quarantine lives.

8. **Restart gateway** so skill slash-commands refresh (running instance
   keeps stale skills until restart):
   `nohup ~/.daedalus/venv/bin/python -m hermes_cli.main gateway run --replace
   > ~/.daedalus/logs/gateway-restart.log 2>&1 &`

## Pitfalls

- `ls` is aliased to eza/exa with icons → error
  `invalid value '...' for '--icons'`. Use `[ -f "$f" ]` test or
  `/usr/bin/ls`, never bare `ls` with paths.
- Always `cd ~/.daedalus` first — relative skill paths fail from other dirs.
- Gateway log may show "Discord slash command limit reached (100): 248
  skill(s) not registered" — normal Discord limit, NOT an error.
- `skills_sync.py`: `_get_bundled_dir()` defaults to `~/.daedalus/skills`
  itself (self-referential) — deleted skills are cleaned from manifest,
  NEVER resurrected. Safe.
- The current session's skill inventory is loaded at start — a cleanup only
  shows in a NEW session.
- Offer the optional follow-up (scrub "neural memory" mentions in kept
  skills) but do NOT do it unprompted.

## Verification checklist

- [ ] SKILL.md count on disk == before − moved
- [ ] quarantine SKILL.md count == moved
- [ ] `.bundled_manifest` line count == new skill count
- [ ] git commit exists; working tree clean for skills/
- [ ] kept skills spot-checked: mazemaker core, file-sync, haus-suche,
      harness-internals, orchestrator all `[ -f ]` OK
- [ ] gateway restarted with --replace
