---
name: linux-workstation-baseline
description: Capture a personal Linux workstation (packages, custom-distro layer, user configs, systemd --user services, system-info snapshots) into a versioned git repo with a self-restoring `restore.sh`. Use when the user says "snapshot my system", "heilige eier", "für den fall der fälle", "verbastelt", "baseline", "reproducible setup", "I want to rebuild my workstation", "save my setup", or asks how to start a personal distro on top of an existing one (Garuda/Endeavour/Manjaro/Arch).
---

# linux-workstation-baseline

Capture a complex personal Linux workstation into a git-tracked, self-restoring baseline. The deliverable is a directory with: package lists, custom-distro-layer inventories, user configs, system-info snapshots, a `README.md`, and an executable `restore.sh`. Optionally pushed to a private remote (GitHub, GitLab, Codeberg, self-hosted).

## When to trigger

- "Heilige Eier", "heilige Zahlen", "für den Fall der Fälle", "verbasteltes System retten"
- User wants to fully rebuild their workstation after a disk failure
- User is on a customized Arch-based distro (Garuda, Endeavour, Manjaro, etc.) and wants to lock in the exact stack
- User is starting a personal distro and wants the baseline before adding ISO/repo layers

## Conventions to confirm first

Before creating the repo, check the user's existing layout — don't break it:

```bash
ls ~/git ~/repos ~/code ~/projects 2>/dev/null   # find their repo convention
git config --global user.name                     # git identity?
git config --global user.email
which gh && gh auth status                        # GitHub CLI available?
```

Common convention: `~/code/<repo-name>/`. Use `~/.config/` style naming for gitignore, README naming, etc.

## Step-by-step

### 1. Inventory system BEFORE creating structure

Run live checks first so you know what's actually present. Never guess paths.

```bash
# Package lists (Arch-based)
pacman -Qqen                    # official repo packages (no AUR)
pacman -Qqem                    # AUR + foreign packages
pacman -Qqet                    # explicit + optional deps
pacman -Qqg base base-devel xorg

# Distribution-specific layer (Garuda example; substitute distro name)
ls /usr/lib/<distro>/
ls /usr/bin/<distro>-*
ls /usr/share/libalpm/hooks/<distro>-*
pacman -Q | grep -i <distro>

# Custom AUR repos (chaotic-aur for Garuda, etc.)
cat /etc/pacman.d/chaotic-mirrorlist
pacman-conf | grep -i chaotic

# User configs (often NOT in /etc/skel/)
ls -la ~/.config/i3/ ~/.config/polybar/
ls -la ~/bin/
ls -la ~/.config/systemd/user/

# System info for restore verification
uname -a
cat /etc/os-release
lsblk -f
cat /etc/fstab
systemctl list-unit-files --state=enabled
```

Pre-flight prevents copying phantom paths.

### 2. Create repo structure

```
<baseline-repo>/
├── README.md
├── restore.sh                  # --dry-run / --confirm
├── .gitignore
├── packages/
│   ├── official.txt
│   ├── aur.txt
│   ├── explicit-top-group.txt
│   ├── groups-meta.txt
│   └── all.txt
├── <distro>-layer/             # e.g. garuda-layer/
│   ├── lib-<distro>.txt
│   ├── usr-bin-<distro>.txt
│   ├── hooks.txt
│   ├── master-hook.txt
│   ├── <distro>-mirrorlist.txt
│   ├── pacman-conf.txt
│   ├── <distro>-packages-installed.txt
│   └── kernels-installed.txt
├── configs/
│   ├── <wm>/                   # i3, sway, hyprland
│   ├── <bar>/                  # polybar, waybar
│   ├── shell/                  # bashrc, zshrc, profile
│   ├── x11/                    # xinitrc, Xresources, xprofile
│   ├── scripts/bin/            # ~/bin contents
│   └── systemd/user/           # full tree incl. default.target.wants/ symlinks
└── system-info/
    ├── kernel.txt
    ├── os-release.txt
    ├── lsblk.txt
    ├── fstab.txt
    └── systemd-enabled.txt
```

### 3. Export package lists + report counts

```bash
REPO=/path/to/repo/packages
pacman -Qqen > $REPO/official.txt
pacman -Qqem > $REPO/aur.txt
pacman -Qqet > $REPO/explicit-top-group.txt
pacman -Qqg base base-devel xorg > $REPO/groups-meta.txt 2>/dev/null
pacman -Qq --color=never > $REPO/all.txt
```

Always report counts ("N official + M AUR + K explicit = T total") — these become the "heilige Zahlen" the user references later.

### 4. Capture custom-distro layer

Run inventory commands from step 1 with output redirected into the corresponding files. Critical paths:

- `/usr/lib/<distro>/` and `/usr/bin/<distro>-*` — the actual tweak scripts
- `/usr/share/libalpm/hooks/<distro>-*` — pacman hooks (1 master hook that triggers others is normal)
- `/etc/pacman.d/<distro>-mirrorlist` and `pacman.conf` blocks — repo source config

### 5. Copy user configs (verify before copy)

Use Python with `os.path.exists` checks — never copy phantom paths:

```python
import shutil, os
HOME = os.path.expanduser("~")
mappings = [
    (f"{REPO}/configs/i3/config", f"{HOME}/.config/i3/config"),
    (f"{REPO}/configs/polybar/config.ini", f"{HOME}/.config/polybar/config.ini"),
    # ... etc.
]
for dst, src in mappings:
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
```

**Critical: preserve `default.target.wants/` symlinks.** They encode which services are enabled — losing them means losing the "enabled services" signal on restore. Verify with `find <dst> -type l | wc -l` after copying.

### 6. Write README.md

Sections:
- Profile (hardware, OS, WM, kernel, package counts)
- Tree structure (one-line per entry)
- Restore procedure (numbered steps)
- Pitfalls (custom-repo keys, /etc/skel/ might be empty, selective service reactivation)
- Snapshot date + counts

### 7. Write restore.sh

Use `--dry-run` (default) / `--confirm` flag pattern. Sections:
1. Activate custom repos (keyring + mirrorlist first)
2. Install official packages via `pacman -S --needed - < official.txt`
3. Install AUR packages via `yay -S --needed - < aur.txt` (assume AUR helper installed separately)
4. Roll out configs (cp + chmod +x)
5. Reactivate systemd --user services (LIST them — don't blindly enable)
6. Run distro update (`<distro>-update`)

### 8. Write .gitignore

Always protect:
- `**/id_rsa`, `**/id_ed25519`, `**/.ssh/`
- `**/.gnupg/`
- `**/.netrc`, `**/.config/gh/hosts.yml`
- `*.bak.rej`, `*.orig`, `*.rej`
- `__pycache__/`, `*.pyc`
- `*.pid`, `*.sock`, `*.log`

### 9. Git init + commit + optional remote push

```bash
cd <REPO>
chmod +x restore.sh
git init -b main
git add -A
git -c commit.gpgsign=false commit -m "Initial baseline snapshot: ..."
```

For remote (GitHub):
```bash
gh repo create <name> --private --source=. \
    --description "..." --remote=origin --push
```

For other remotes: ask user for URL.

## Pitfalls

1. **`/etc/skel/` is NOT always empty — CHECK first.** On a vanilla Arch install with no
   meta-packages, `/etc/skel/` is empty. But on Garuda, Endeavour, Manjaro, and most
   "user-friendly" derivatives, it's FULL of distro defaults — typically 40-60 files
   including `.config/{autostart,bleachbit,deluge,falkon/profiles/<distro>,fish,libreoffice,
   micro/<plug>/*,mpv,pacseek,vlc}`, `.config/starship.toml`, `.config/environment.d/<browser>.conf`,
   `.screenrc`, `.bashrc`, `.bashrc_<distro>`, `.bash_profile`, `.bash_logout`, and
   `.local/share/<tool>/...`. Always `ls -la /etc/skel/` and walk the full tree — these
   ARE the defaults that land in every new user's home. Capture them.

2. **Don't blindly re-enable all systemd --user services.** Many are project-specific (mazemaker, hermes, btquant, etc.). On restore, list them and let the user pick.

3. **Custom repo keys (chaotic-aur etc.) MUST be present before AUR packages can be installed.** Restore script must import the keyring first: `pacman-key --recv-key <KEY> --keyserver keyserver.ubuntu.com && pacman -U https://<mirror>/.../chaotic-keyring.pkg.tar.zst`.

4. **AUR helpers (yay/paru) are NOT in the official repo.** Must be installed manually before `aur.txt` can be processed. Either `git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si` first, or document this as a restore prerequisite.

5. **Service files contain absolute paths to user home and binaries.** They are NOT portable across machines. Restore is for SAME machine (or same user setup on similar hardware), not for cloning to a different box.

6. **Distro-specific tools (e.g., `garuda-update`) require the distro's metapackage installed.** Pure Arch install won't have them. For pure-Arch restore: install Garuda/Manjaro/etc. first OR skip the `<distro>-update` step.

7. **GitHub API may return 404 immediately after `gh repo create`.** Wait 30–60s for propagation. `gh repo view` works before the REST API does — use that for verification.

8. **`pacman -Qqet` returns "explicit + optional" packages** — different from `pacman -Qqen` which is "official + explicit". The three together (official/aur/explicit) give a complete picture of user intent vs. auto-installed deps.

9. **The user's i3/waybar/etc. config may be versioned as named editions** (e.g., "Hermelin Edition v6"). Preserve the branding string in the README and commit message — it's identity, not decoration.

## Verification

After commit:
- `bash -n restore.sh` — syntax check passes
- `git ls-files | wc -l` — count matches expected (typically 80–150)
- Sanity grep on critical packages: `grep -E '^(i3|polybar|picom|rofi|xorg-server|linux-zen)$' packages/official.txt`
- `du -sh .` — total size < 2MB (configs are tiny; if larger, audit for accidental binary copies)
- `git status` — working tree clean
- `gh repo view <user>/<repo>` (or `git ls-remote`) — confirms push to remote

## Templates and references

- `templates/restore.sh` — full 6-step restore script with --dry-run/--confirm
- `templates/README.md` — baseline README structure with sections to fill
- `templates/.gitignore` — minimum-protection gitignore
- `references/garuda-specific.md` — Garuda-Linux-specific layer details (where tweaks live, chaotic-aur keyring, garuda-update tool paths)

## Companion: capturing a baseline (absorbed from `linux-system-baseline-capture`)

The capture workflow — snapshotting a live personal Linux workstation (packages,
custom configs, AUR/build state) into a restorable baseline repo — was absorbed from
`linux-system-baseline-capture`. This skill (workstation-baseline) is the *apply* side;
the capture side's detail lives in the re-homed support below and should be consulted
when first building the baseline repo that this skill later restores.

- `references/linux-system-baseline-capture/` — capture methodology notes.
- `templates/linux-system-baseline-capture/` — capture-time templates.
- `scripts/linux-system-baseline-capture/` — capture helpers.

## Cross-reference

- Memory: `fact:garuda-i3-baseline-repo` (824417), `fact:hermelin-edition-i3-setup` (824418), `fact:github-repos-inventory` (824419) — the actual baseline instance built using this workflow