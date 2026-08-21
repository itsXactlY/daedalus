# Garuda-spezifische Layer-Details

Notizen zur Inventarisierung eines Garuda-Linux-Systems für das `linux-workstation-baseline`-Repo.

## Wo Garuda-Tweaks leben

| Pfad | Inhalt | Inventar-Datei |
|---|---|---|
| `/usr/lib/garuda/` | 9 Helper-Skripte (release, shlib, update, install-software, is-snapshot-boot, launch-terminal, pacdiff-merge, pkexec-gui, qrcode) | `garuda-layer/lib-garuda.txt` |
| `/usr/bin/garuda-*` | 10 User-Tools (boot-options, diag, hardware-tool, health, inxi, network-assistant, privatebin, system-maintenance, toolbox, update) | `garuda-layer/usr-bin-garuda.txt` |
| `/usr/share/libalpm/hooks/garuda-hooks-runner.hook` | 1 Master-Hook (triggert alle anderen Garuda-Hooks) | `garuda-layer/master-hook.txt` |
| `/etc/pacman.d/chaotic-mirrorlist` | Chaotic-AUR Mirror-Config (Garuda's AUR-Quelle) | `garuda-layer/chaotic-mirrorlist.txt` |

## Chaotic-AUR — Restore-Voraussetzung

Bevor AUR-Pakete installiert werden können, muss chaotic-aur als Repo aktiv sein:

```bash
pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com
pacman-key --lsign-key 3056513887B78AEB
pacman -U 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst'
pacman -U 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst'
```

Key-Fingerprint: `3056513887B78AEB` (garuda@chaotic.cx). Falls der Mirror down ist: Backup-Mirror unter `https://aur.chaotic.cx/`.

## Garuda-Metapakete

Bei einer frischen Garuda-Installation sind folgende Metapakete typisch installiert (siehe `garuda-layer/garuda-packages-installed.txt` für die echte Liste dieses Systems):

- `garuda-common` — Basis-Tweaks, Hooks, Helper
- `garuda-zsh-config` — ZSH-Defaults (falls ZSH genutzt)
- `garuda-hooks` — pacman-Hook-Sammlung
- `garuda-settings` — Garuda-Anpassungen
- `garuda-update` — Update-Tool

Diese Pakete ziehen den Tweak-Layer automatisch nach `/usr/lib/garuda/` und `/usr/bin/garuda-*`. Manuell kopieren ist NICHT nötig, wenn die Pakete selbst installiert werden.

## Was Garuda anders macht als Vanilla-Arch

1. **Modifizierte initramfs** mit BTRFS-overlay (für Timeshift-Snapshots) — lebt in `/etc/mkinitcpio.d/`
2. **Automatische Kernel-Patches** über pacman-Hook (z.B. für NVIDIA)
3. **BTRFS-Snapshots** via `btrfs-assistant` und `snapper` — Garuda-Default für Timeshift-Integration
4. **Chaotic-AUR Repo** als Standard-AUR-Quelle (schneller als manueller AUR-Build)
5. **`garuda-update` CLI** als zentrales Update-Tool (statt `pacman -Syu` direkt)

## Für Distro-Aufbau relevant

Wenn aus dem Baseline ein echtes Custom-Distro werden soll (siehe Gesprächsnotizen zu den 3 Phasen), sind die Garuda-PKGBUILDs relevant:

- Source: `https://github.com/garuda-linux/pkgbuilds`
- Diese enthalten die `garuda-common`, `garuda-hooks`, `garuda-update`-Rezepte
- Im Baseline-Inventar nur die INSTALLIERTEN Pakete listen, nicht die PKGBUILDs selbst

## Wichtige Config-Pfade (Garuda-default, falls user nicht überschrieben)

| Datei | Was |
|---|---|
| `/etc/pacman.d/chaotic-mirrorlist` | Chaotic-AUR Mirror (s.o.) |
| `/etc/mkinitcpio.d/linux-zen.preset` | Kernel-Initramfs-Defaults |
| `/etc/snapper/configs/root` | BTRFS-Snapshot-Config |
| `/etc/polkit-1/rules.d/garuda.rules` | Polkit-Regeln für Garuda-Tools |

Diese sind Teil der Metapakete und werden mit `pacman -S garuda-common` etc. restored — nicht manuell kopieren.

## Bekannte Quirks

- **`/etc/skel/` ist auf Garuda-Default-Installationen LEER** — die Defaults werden erst beim ersten User-Login via `garuda-assistant` auf den User-Account kopiert. Nach Restore muss ggf. `garuda-assistant` einmal manuell laufen.
- **`garuda-update` braucht `chaotic-aur` zwingend** — sonst schlägt der Update fehl mit "missing keyring".
- **Bei NVIDIA-Systemen** hat Garuda eigene Hooks für automatischen Kernel-Patch — bei reinem Arch-Restore gehen die verloren.