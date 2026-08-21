---
name: daedalus-skillpack
description: Bundle, verify, and install Daedalus skills as portable skillpacks (.skillpack.zip) — pack/list/info/verify/unpack
version: 1.0.0
tags: [daedalus, skills, packaging, skillpack, distribution]
created: 2026-08-10
---


> Ported from `hermes-skillpack` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Skillpack Tool

Bundles skills into a single self-describing, checksummed `.skillpack.zip` that
can be moved to another machine and installed with one command.

Tool: `~/.daedalus/tools/skillpack.py` (symlinked as `~/.daedalus/bin/skillpack`).
Output dir: `~/.daedalus/skillpacks/`. Docs: `~/.daedalus/skillpacks/README.md`.

## Commands

    skillpack list [--category CAT]       # what can I pack? (340 skills)
    skillpack pack NAME skill...          # named skills
    skillpack pack NAME --category CAT    # whole category
    skillpack pack NAME --all             # entire library
        [--version V] [--description D] [--out DIR]
    skillpack info ARCHIVE                # show manifest
    skillpack verify ARCHIVE              # zip + checksums + frontmatter
    skillpack unpack ARCHIVE [--dir D] [--force]

## Format

    manifest.json          # format: daedalus-skillpack v1, per-file sha256 checksums
    skills/<cat>/<skill>/… # categorized skills
    skills/<skill>/…       # flat skills (no category dir)

- `unpack` refuses to overwrite existing skills unless `--force`.
- `verify` checks: zip integrity, every declared file exists + checksum matches,
  no undeclared files, every SKILL.md has YAML frontmatter.

## Skill tree layout (why discovery is recursive)

Mixed nesting: `skills/<skill>/SKILL.md` (flat), `skills/<cat>/<skill>/SKILL.md`,
`skills/<cat>/<sub>/<skill>/SKILL.md`. `discover_skills` uses rglob and derives
category from the relative path parts; flat skills get category "".

## Critical pitfall — flat skill dirs that contain categorized siblings

Some flat skills SHARE their directory with categorized skills:
`skills/dogfood/SKILL.md` + `skills/dogfood/clean-restart/SKILL.md`,
`skills/dayz-mod-development/SKILL.md` + `skills/dayz-mod-development/dayz-*/`.
`collect_files` must skip any file inside a subdirectory that has its own SKILL.md
(`_is_nested_skill_file`), otherwise the flat skill absorbs the nested skills and
the zip gets duplicate arcs ("Duplicate name" warnings). Verified: full-library pack
= 340 skills / 2028 files / 0 dup arcs.

## Verified round-trip

pack --all → unpack to temp dir → re-pack from temp → verify: all pass.
