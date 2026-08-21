# Arch-Based System Baseline — Concrete Recipe

**Goal**: capture an Arch-based install (Arch / Garuda / Manjaro / Endeavour / etc.) into a versioned repo, in one pass.

## Pre-flight

```bash
# Confirm root of capture
ls /etc/arch-release /etc/os-release 2>/dev/null

# Note the distro NAME for Layer 3 detection
grep '^NAME=' /etc/os-release

# Note user home for Layer 2 (capture from $HOME, not /home/* if non-standard)
echo "$HOME"
```

## Step 1: Create repo skeleton

```bash
REPO="$HOME/code/$(hostname)-baseline"   # user convention: ~/code/<project>
mkdir -p "$REPO"/{packages,configs,update-lifecycle,scripts,system-info}
mkdir -p "$REPO"/configs/{i3,polybar,shell,x11,systemd/user,scripts/bin}
mkdir -p "$REPO"/update-lifecycle/{hooks,runner-scripts,lib-garuda,tools,etc}
```

## Step 2: Layer 1 — Packages

```bash
cd "$REPO"
pacman -Qqen > packages/official.txt
pacman -Qqem > packages/aur.txt
pacman -Qqet > packages/explicit.txt
pacman -Qq  > packages/all.txt

# Sanity
wc -l packages/*.txt
# Expect: official.txt ~hundreds, aur.txt ~0-50, explicit.txt ~hundreds, all.txt ~thousands
```

## Step 3: Layer 2 — Configs

```bash
HOME_DIR="$HOME"
cd "$REPO"

# Standard user configs — best-effort (skip missing)
for src_dst in \
    "$HOME_DIR/.config/i3/config:configs/i3/config" \
    "$HOME_DIR/.config/i3/config.local:configs/i3/config.local" \
    "$HOME_DIR/.config/polybar/config.ini:configs/polybar/config.ini" \
    "$HOME_DIR/.config/polybar/launch.sh:configs/polybar/launch.sh" \
    "$HOME_DIR/.zshrc:configs/shell/zshrc" \
    "$HOME_DIR/.bashrc:configs/shell/bashrc" \
    "$HOME_DIR/.bash_profile:configs/shell/bash_profile" \
    "$HOME_DIR/.xinitrc:configs/x11/xinitrc" \
    "$HOME_DIR/.Xresources:configs/x11/Xresources"; do
    src="${src_dst%:*}"
    dst="${src_dst#*:}"
    [[ -f "$src" ]] && cp "$src" "$dst"
done

# CRITICAL: check /etc/skel/ — often non-empty on derivative distros
ls -la /etc/skel/
[[ -f /etc/skel/.bashrc_garuda ]] && cp /etc/skel/.bashrc_garuda configs/skel/.bashrc_garuda
# (or whatever the distro's skel file is)

# User scripts
[[ -d "$HOME_DIR/bin" ]] && cp -r "$HOME_DIR/bin" configs/scripts/

# User systemd services (often contains custom infra: hermes, mazemaker, btquant, etc.)
[[ -d "$HOME_DIR/.config/systemd/user" ]] && cp -r "$HOME_DIR/.config/systemd/user" configs/systemd/
```

## Step 4: Layer 3 — Distro machinery

Heuristic: capture everything in distro-named dirs.

```bash
cd "$REPO"
DISTRO=$(grep '^NAME=' /etc/os-release | cut -d= -f2 | tr -d '"' | tr 'A-Z' 'a-z')
DISTRO_DIR="update-lifecycle"   # or "<distro>-layer"

# Generic capture for any Arch-derivative
for path in \
    "/usr/lib/$DISTRO" \
    "/usr/bin/${DISTRO}-"* \
    "/etc/$DISTRO" \
    "/etc/${DISTRO}-settings" \
    "/etc/default/grub.d/*${DISTRO}*" \
    "/etc/logrotate.d/${DISTRO}-*" \
    "/etc/xdg/autostart/${DISTRO}-*.desktop" \
    "/etc/snapper/config-templates/$DISTRO"; do
    [[ -e "$path" ]] && cp -r "$path" "$DISTRO_DIR/" 2>/dev/null
done

# Pacman hooks (all distro-related)
for hook in /usr/share/libalpm/hooks/*${DISTRO}* \
            /usr/share/libalpm/hooks/snap-pac* \
            /usr/share/libalpm/hooks/*linux-modules* \
            /usr/share/libalpm/hooks/*dracut* \
            /usr/share/libalpm/hooks/*grub-install* \
            /usr/share/libalpm/hooks/*lsb-release* \
            /usr/share/libalpm/hooks/*os-release* \
            /usr/share/libalpm/hooks/*systemd-sysctl*; do
    [[ -f "$hook" ]] && cp "$hook" "$DISTRO_DIR/hooks/"
done

# Runner scripts
for s in /usr/share/libalpm/scripts/*${DISTRO}*; do
    [[ -x "$s" ]] && cp "$s" "$DISTRO_DIR/runner-scripts/" && chmod +x "$DISTRO_DIR/runner-scripts/$(basename $s)"
done
```

## Step 5: Layer 4 — Update lifecycle documentation

Write `update-lifecycle/LIFECYCLE.md` enumerating every hook trigger. See `references/garuda-update-lifecycle.md` for the Garuda template.

```bash
cd "$REPO"
# Auto-generate skeleton
{
    echo "# Update Lifecycle"
    echo
    echo "## Pre-Transaction Hooks"
    for h in update-lifecycle/hooks/*pre*.hook; do
        [[ -f "$h" ]] && echo "- $(basename "$h")"
    done
    echo
    echo "## Post-Transaction Hooks"
    for h in update-lifecycle/hooks/*post*.hook update-lifecycle/hooks/*install*.hook; do
        [[ -f "$h" ]] && echo "- $(basename "$h")"
    done
} > update-lifecycle/LIFECYCLE.md
```

## Step 6: Layer 6 — Runtime snapshot

```bash
cd "$REPO"
uname -a                       > system-info/kernel.txt
cat /etc/os-release            > system-info/os-release.txt
lsblk -f                       > system-info/lsblk.txt 2>/dev/null
cat /etc/fstab                 > system-info/fstab.txt
systemctl list-unit-files --state=enabled > system-info/systemd-enabled.txt
```

## Step 7: Write restore.sh

Copy from `templates/restore-script.sh`, customize per the captured package lists and configs.

## Step 8: Write README.md

Must include:

- Hardware profile
- OS + kernel + DE/WM
- Package counts (official / AUR / explicit / total)
- Restore-Anleitung (3-5 commands)
- Pitfalls (chaotic-aur keyring, garuda-keyring, snapper manual setup, etc.)

## Step 9: .gitignore

```gitignore
**/id_rsa
**/id_ed25519
**/.ssh/
**/.gnupg/
**/.netrc
**/.config/gh/hosts.yml
*.bak
*.tmp
*.log
```

## Step 10: Git init + push

```bash
cd "$REPO"
git init -b main
git add -A
git -c commit.gpgsign=false commit -m "Initial baseline snapshot: $(hostname) on $(grep PRETTY /etc/os-release | cut -d= -f2 | tr -d '"')"
gh repo create "$(basename "$REPO")" --private --source=. --remote=origin --push
```

## Verify before declaring done

```bash
cd "$REPO"
echo "=== Counts ==="
wc -l packages/*.txt
echo "Files: $(git ls-files | wc -l), Size: $(du -sh . | cut -f1)"
echo
echo "=== Layer check ==="
for layer in packages configs update-lifecycle scripts system-info; do
    if [[ -d "$layer" ]]; then
        count=$(find "$layer" -type f | wc -l)
        echo "  $layer: $count files"
    else
        echo "  ✗ $layer MISSING"
    fi
done
```

## Optional: write install-<distro>-on-<base>.sh

Use `templates/idempotent-installer.sh` as the starting point. Custom-tailor for the specific distro's repo keys and packages.

Key requirements:

- `--dry-run` + `--confirm` modes
- Idempotency check before each step (`pacman -Q <pkg>`, `ls <file>`, etc.)
- Final step: per-component ✓/✗ verification

## Done checklist

- [ ] `packages/*.txt` populated
- [ ] `configs/` has user configs from `$HOME`
- [ ] `/etc/skel/` checked and captured (often non-empty)
- [ ] Distro machinery captured (helper lib, tools, etc/)
- [ ] All distro-related pacman hooks captured
- [ ] `LIFECYCLE.md` written
- [ ] `system-info/` populated
- [ ] `restore.sh` written + bash-syntax-checked
- [ ] `README.md` written
- [ ] `.gitignore` protects secrets
- [ ] `git status` clean
- [ ] Pushed to GitHub
- [ ] Counts match expectations