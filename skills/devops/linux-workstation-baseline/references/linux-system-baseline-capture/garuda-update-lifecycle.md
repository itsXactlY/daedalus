# Garuda Update Lifecycle — Worked Example

**Source**: Live snapshot of ThinkPad P50 Garuda Linux install, captured 2026-06-20.

This is what `garuda-update` actually does — it's much more than `pacman -Syu`.

## The 3 trigger mechanisms

1. **`garuda-update`** binary — user-invoked entry point (`/usr/bin/garuda-update`, 4KB)
2. **pacman hooks** — auto-trigger on pacman operations (`/usr/share/libalpm/hooks/`, 20 distro-related files)
3. **`garuda-system-maintenance`** — daily systemd-timer (138KB binary)

## Pre-Transaction hooks (3)

| Hook | Trigger | Action |
|------|---------|--------|
| `05-snap-pac-pre.hook` | every pacman op | snapper pre-snapshot (**AbortOnFail** — update aborts if snapshot fails) |
| `50-garuda-config-agent-pre.hook` | `/etc/*` change | `garuda-config-agent pre` (backup user configs) |
| `10-linux-modules-pre.hook` | kernel modules | prepare modules |

## Post-Transaction hooks (17)

| Hook | Trigger | Action |
|------|---------|--------|
| `garuda-hooks-runner.hook` | garuda-hooks upgraded | master runner |
| `00-garuda-migrations.hook` | garuda-migrations upgraded | migrations runner |
| `000-garuda-config-agent-post.hook` | `/etc/*` change | config-agent `post` (merge) |
| `000-garuda-config-agent-postinst.hook` | install only | config-agent `postinst` |
| `10-linux-modules-post.hook` | kernel modules | reload |
| `20-grub-btrfs-config.hook` | grub-btrfsd | BTRFS in GRUB |
| `20-lsb-release.hook` | lsb-release | regenerate |
| `20-os-release.hook` | os-release | regenerate |
| `25-systemd-sysctl.hook` | systemd-sysctl | apply sysctl |
| `60-dracut-remove.hook` | dracut | remove old initramfs |
| `90-dracut-install.hook` | dracut/firmware | **rebuild initramfs** |
| `99-grub-install.hook` | grub | GRUB binary in EFI |
| `01-snapshot-reject.hook` | transaction fail | reject bad snapshot |
| `firedragon-post.hook` | firedragon | browser post-setup |
| `firefox-post.hook` | firefox | browser post-setup |
| `firefox-dev-post.hook` | firefox-developer | dev edition post |
| `firefox-kde-post.hook` | firefox-kde | KDE firefox post |

## 3 runner binaries (`/usr/share/libalpm/scripts/`)

- **`garuda-config-agent`** (15KB) — `pre`/`post`/`postinst` subcommands, uses 73KB SQLite DB (`/etc/garuda/garuda-config-agent/configs.db`) to track user config choices across updates
- **`garuda-hooks-runner`** (8KB) — master + `grub-update` subcommand
- **`garuda-migrations-runner`** (16KB) — one-shot migrations, tracked via `/etc/garuda/migrations/applied_version`

## 10 user tools (`/usr/bin/garuda-*`)

| Tool | Size | Purpose |
|------|------:|---------|
| `garuda-update` | 4KB | main update |
| `garuda-system-maintenance` | 138KB | daily timer + interactive maintenance |
| `garuda-boot-options` | 358KB | GRUB/snapshot/kernel UI |
| `garuda-network-assistant` | 378KB | NetworkManager UI |
| `garuda-health` | 60KB | system diagnosis |
| `garuda-hardware-tool` | 6KB | hw profile detection |
| `garuda-toolbox` | 1KB | tool wrapper |
| `garuda-diag` | 3KB | diagnostic helper |
| `garuda-inxi` | 4KB | system info via inxi |
| `garuda-privatebin` | 310B | privatebin upload for diagnostics |

## Helper library (`/usr/lib/garuda/`)

9 helper files:

- `garuda-release` (36B) — version string
- `garuda.shlib` (210B) — bash library
- `install-software` (278B) — meta-package helper
- `is-snapshot-boot` (189B) — detect snapshot boot
- `launch-terminal` (2.3KB)
- `pacdiff-merge` (2KB)
- `pkexec-gui` (2.3KB)
- `qrcode` (1KB)
- `garuda-update/` subdirectory with 4 scripts:
  - `auto-pacman` (6.2KB)
  - `help` (2.5KB)
  - `main-update` (10KB) — main update logic
  - `update-helper-scripts` (11.6KB) — helper collection

## State directories

- `/etc/garuda/garuda-config-agent/` — 9 files + 73KB SQLite `configs.db`
  - `btrfsmaintenance.yaml`, `faillock.yaml`, `grub.yaml`, `locale-gen.yaml`,
    `nsswitch.yaml`, `pacman.yaml`, `paru.yaml`, `updatedb.yaml`
- `/etc/garuda/garuda-update/` — `config`, `intervention_sequence`
- `/etc/garuda/migrations/` — `applied_version`, `has_legacy_patches`
- `/etc/garuda/health/` — health cache (empty until first diag)
- `/var/lib/garuda/last_update` — timestamp marker
- `/var/log/garuda/` — log files (rotated: daily, rotate 7, maxsize 2M)

## Application defaults

- `/etc/garuda-settings/` — 6 INI files configuring browser variants:
  - `garuda-firedragon.ini` (2KB), `garuda-firefox.ini` (1.4KB)
  - `garuda-firefox-developer-edition.ini` (1.4KB), `garuda-firefox-kde.ini` (1.4KB)
  - `garuda-librewolf.ini` (1.4KB), `garuda-thunderbird.ini` (189B)

## GRUB + boot

- `/etc/default/grub.d/00_garuda-kernel-params.cfg` — `GRUB_DISABLE_OS_PROBER=false`
- `/etc/default/grub.d/20-garuda-dracut-support.cfg` — `GRUB_EARLY_INITRD_LINUX_STOCK=''` (prevents microcode double-load, observed issue on AMD)
- `/etc/snapper/config-templates/garuda` — snapper template for `create-config /`

## User defaults — NOT empty

- `/etc/skel/.bashrc_garuda` (3KB) — bash config template for new users
- (Common misconception: `/etc/skel/` is "empty" by default — but Garuda drops defaults here. Always verify with `ls -la /etc/skel/`.)

## Autostart

- `/etc/xdg/autostart/garuda-system-maintenance.desktop` — runs `garuda-system-maintenance` on session start

## Logrotate

- `/etc/logrotate.d/garuda-update` — daily, rotate 7, maxsize 2M, noolddir

## The complete snapshot for version control

Total: ~1.4MB, ~72 files across:

- 20 hooks (small text files, 200-1100 bytes each — capture full content, not summaries)
- 3 runner binaries (~40KB combined)
- 9 helper library files + 4 update scripts (~30KB)
- 10 user tool binaries (~1MB combined, biggest are boot-options 358KB and network-assistant 378KB)
- 13+ config files in `/etc/garuda/`
- 6 browser `.ini` files in `/etc/garuda-settings/`
- 2 grub.d tweaks
- 1 logrotate config
- 1 autostart .desktop
- 1 `/etc/skel/.bashrc_garuda`
- 2 snapper configs (config-templates/garuda + stub for configs/root which is root-owned)
- 1 `LIFECYCLE.md` (~15KB documentation)

## Common capture-time mistakes

1. **Forgetting `/etc/skel/.bashrc_garuda`** — looks empty but isn't
2. **Snapper `/etc/snapper/configs/root`** is root-owned, PermissionError on user-copy — document via stub, recreate via `sudo snapper create-config /`
3. **`/var/lib/snapper/`, `/var/cache/pacman/pkg/`, `/var/log/`** are not versionable
4. **Assuming "user-config" means `~/.config`** — also `/etc/skel/`, `/usr/local/`, polkit rules, systemd-timers, cron.d