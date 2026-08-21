---
name: daedalus-skill-discovery-debugging
description: Debug why Daedalus skills don't appear in skills_list or fail to load via skill_view — rglob symlink limitation, category field requirements, and skill discovery internals.
category: software-development
---


> Ported from `hermes-skill-discovery-debugging` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Skill Discovery Debugging

## When to Use
When a skill directory exists at `~/.daedalus/skills/<category>/<name>/` but:
- `skills_list` doesn't show it
- `skill_view('name')` fails or returns nothing
- The skill was previously working and suddenly disappeared
- A newly created skill isn't being picked up

## How Daedalus Discovers Skills

### Source: `hermes-agent/tools/skills_tool.py`

`_find_all_skills()` does:
```python
SKILLS_DIR = Path.home() / ".daedalus" / "skills"
for sk in SKILLS_DIR.rglob("SKILL.md"):
    # excludes .git, .github, .hub in path parts
    # deduplicates by parent.name
    skills.append(self._load_skill(sk))
```

`_load_skill()` reads the YAML front matter, requires `name` and `category` fields.

### Source: `hermes-agent/agent/skill_utils.py`

`get_external_skills_dirs()` reads `skills.external_dirs` from `config.yaml`. This is an **alternative** approach — skills outside `~/.daedalus/skills/` can be discovered via config instead of being copied inside.

---

## Critical: Python rglob Does NOT Follow External Directory Symlinks

This is the #1 reason skills fail to be discovered.

### The Problem

`Path.rglob()` does **NOT** descend into directory symlinks when the resolved (real) target is **outside** the scan root tree.

Example that FAILS:
```
~/.daedalus/skills/devops/pulse/ → /home/alca/projects/pulse/  (external symlink)
```

When `_find_all_skills()` calls `SKILLS_DIR.rglob("SKILL.md")`:
- `SKILLS_DIR = ~/.daedalus/skills/`
- `~/.daedalus/skills/devops/pulse` is a symlink to `/home/alca/projects/pulse`
- `realpath(~/.daedalus/skills/devops/pulse)` → `/home/alca/projects/pulse` (OUTSIDE scan root)
- rglob skips it — **the skill is never visited**

### Why `pulse-source-debugging` Worked but `pulse` Didn't

Both had `category: research` / `category: devops`. But:
- `pulse-source-debugging` was a **real directory** inside `~/.daedalus/skills/`
- `pulse` was a **symlink** pointing outside → rglob skipped it

### The Fix: Copy Files, Don't Symlink External Directories

Install scripts that create skills MUST copy skill content as real files inside `~/.daedalus/skills/`:
```bash
# WRONG — symlink to external dir, rglob won't find it
ln -sf /home/user/projects/myproject ~/.daedalus/skills/devops/myproject

# RIGHT — copy as real directory inside skills tree
cp -r /home/user/projects/myproject/scripts ~/.daedalus/skills/devops/myproject/scripts
cp /home/user/projects/myproject/SKILL.md ~/.daedalus/skills/devops/myproject/SKILL.md
```

### File Symlinks Are Fine

File symlinks (not directory symlinks) don't have this issue — rglob follows them:
```bash
# OK — CLI binary as file symlink, doesn't affect rglob
ln -sf ~/.daedalus/skills/devops/pulse/scripts/pulse.py ~/.local/bin/pulse
```

### Alternative: Use `skills.external_dirs` in config.yaml

Instead of copying, add an external directory to `config.yaml`:
```yaml
skills:
  external_dirs:
    - /home/user/projects/myproject
```

Then `get_external_skills_dirs()` in `skill_utils.py` will include it. But `_find_all_skills()` still uses rglob on `SKILLS_DIR` only — the external_dirs path is used separately. Check if your Daedalus version actually uses `get_external_skills_dirs()` in `_find_all_skills()`.

---

## Debugging Steps

### 1. Check if rglob Finds the Skill

```python
from pathlib import Path
SKILLS_DIR = Path.home() / ".daedalus" / "skills"

# List all SKILL.md found by rglob
found = list(SKILLS_DIR.rglob("SKILL.md"))
print(f"rglob found {len(found)} SKILL.md files")
for f in found:
    print(f"  {f.relative_to(SKILLS_DIR)}")
```

### 2. Check if the Directory Is a Symlink

```python
skill_dir = SKILLS_DIR / "devops" / "pulse"
print(f"Is symlink: {skill_dir.is_symlink()}")
if skill_dir.is_symlink():
    print(f"Real path: {skill_dir.resolve()}")
    print(f"Resolves inside SKILLS_DIR: {skill_dir.resolve().is_relative_to(SKILLS_DIR)}")
```

### 3. Check the SKILL.md YAML Front Matter

```python
import yaml
skill_file = SKILLS_DIR / "devops" / "pulse" / "SKILL.md"
content = skill_file.read_text()
front_matter = yaml.safe_load(content.split("---")[1])
print(f"name: {front_matter.get('name')}")
print(f"category: {front_matter.get('category')}")  # Must be truthy!
```

### 4. Simulate Daedalus's Exact Discovery Code

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".daedalus" / "hermes-agent"))

from tools.skills_tool import _find_all_skills
# Instantiate to get the method
class FakeSelf:
    _skill_cache = None
skills = _find_all_skills(FakeSelf())
your_skill = [s for s in skills if s.get("name") == "pulse"]
print(f"Found: {your_skill}")
```

### 5. Check `skills_list` Filter

In `skills_tool.py` lines ~780-795:
```python
if not skill.get("category"):  # Only includes skills with truthy category
    continue
```

If `category` is missing or null in SKILL.md, `skills_list` silently excludes it.

---

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `skills_list` empty | No skills with truthy `category` | Add `category:` field to SKILL.md |
| `pulse` missing but `pulse-source-debugging` works | Directory symlink to external path | Copy files instead of symlinking |
| `skill_view` returns nothing | `_find_all_skills()` never visited the dir | Same as above |
| Skill disappears after git pull | External symlink, git creates new dir? | Copy files |
| `skills_list` shows skill but can't load | `category` missing or skill not in `_find_all_skills()` output | Check YAML front matter |

---

## Verification Checklist

- [ ] `SKILLS_DIR.rglob("SKILL.md")` finds the skill's SKILL.md
- [ ] Skill directory is NOT a symlink to an external path
- [ ] `SKILL.md` has `name:` field set
- [ ] `SKILL.md` has `category:` field set (truthy value)
- [ ] `_find_all_skills()` returns the skill
- [ ] `skills_list` shows the skill
- [ ] `skill_view("name")` returns the skill

---

## Key Files

- `~/.daedalus/tools/skills_tool.py` — `_find_all_skills()`, `skills_list`, `skill_view`
- `~/.daedalus/agent/skill_utils.py` — `get_external_skills_dirs()`
- `~/.daedalus/config.yaml` — `skills.external_dirs` alternative
