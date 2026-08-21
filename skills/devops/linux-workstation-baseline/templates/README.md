# <repo-name>

**Heilige Eier** — Snapshot der Workstation.
Genau dieser Stand, falls die Platte abraucht.

## Profil

- **Hardware**: <ThinkPad-Modell etc.>
- **OS**: <Distro> (<Arch-basiert>) — siehe `system-info/os-release.txt`
- **DE/WM**: <i3, sway, hyprland> + <X11/Wayland>
- **Kernel**: siehe `system-info/kernel.txt` und `<distro>-layer/kernels-installed.txt`
- **Paketbasis**: <N> offiziell + <M> AUR + <K> explizit = <T> Pakete total
- **Distro-Metapakete**: <X> installiert (siehe `<distro>-layer/<distro>-packages-installed.txt`)
- **Display-Manager**: (prüfe `system-info/systemd-enabled.txt`)

## Struktur

```
.
├── README.md                          ← diese Datei
├── .gitignore
├── restore.sh                         ← Wiederherstellungs-Skript (--dry-run / --confirm)
├── packages/
│   ├── official.txt                   ← <N> Pakete aus [core] [extra] [multilib]
│   ├── aur.txt                        ← <M> Pakete aus AUR/custom
│   ├── explicit-top-group.txt         ← <K> explizit installiert (ohne auto-deps)
│   ├── groups-meta.txt                ← base/base-devel/xorg Gruppen
│   └── all.txt                        ← <T> Pakete total (inkl. deps)
├── <distro>-layer/
│   ├── lib-<distro>.txt               ← /usr/lib/<distro>/ (Helper)
│   ├── usr-bin-<distro>.txt           ← /usr/bin/<distro>-* (User-Tools)
│   ├── hooks.txt                      ← pacman-hooks
│   ├── master-hook.txt                ← Inhalt des Master-Hooks
│   ├── <distro>-mirrorlist.txt        ← Distro Mirror-Config
│   ├── pacman-conf.txt                ← pacman.conf Repo-Block
│   ├── <distro>-packages-installed.txt ← pacman -Q | grep <distro>
│   └── kernels-installed.txt          ← linux/linux-zen/linux-lts etc.
├── configs/
│   ├── <wm>/config                    ← <WM> Window-Manager
│   ├── <bar>/{config.ini,launch.sh}   ← Bar-Setup
│   ├── shell/{bashrc,bash_profile}    ← Shell-Defaults
│   ├── x11/{Xresources,xprofile}      ← X11 Session-Setup
│   ├── scripts/bin/                   ← Eigene Skripte aus ~/bin
│   └── systemd/user/                  ← systemd --user Services + .wants/ Symlinks
└── system-info/
    ├── kernel.txt                     ← uname -a
    ├── os-release.txt                 ← /etc/os-release
    ├── lsblk.txt                      ← Disk-Layout (verifizierbar gegen fstab)
    ├── fstab.txt                      ← Mount-Points
    └── systemd-enabled.txt            ← systemctl list-unit-files --state=enabled
```

## Restore (Trockenlauf)

```bash
# Frisches Arch-Mini oder Distro-ISO booten, chroot vorbereiten:
# pacstrap /mnt base linux-firmware
# arch-chroot /mnt

# 1. Pakete installieren (Reihenfolge: offiziell → AUR)
pacman -S --needed - < packages/official.txt

# 2. AUR-Helper bereitstellen, dann AUR-Pakete
# (pacman -S --needed git base-devel && git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si)
yay -S --needed - < packages/aur.txt

# 3. Configs ausrollen (von hier nach ~/)
cp configs/<wm>/config ~/.config/<wm>/config
cp -r configs/<bar>/* ~/.config/<bar>/
cp configs/shell/bashrc ~/.bashrc
# ... usw. siehe restore.sh für Vollautomatik

# 4. systemd/user Services reaktivieren (gewünschte auswählen!)
systemctl --user daemon-reload
# systemctl --user enable <name>.service
```

Für die volle Automatisierung: `bash restore.sh` (interaktiv mit `--dry-run` oder `--confirm`).

## Wichtige Hinweise

1. **Custom Repo MUSS aktiv sein** bevor AUR-Pakete installiert werden. Siehe `<distro>-layer/<distro>-mirrorlist.txt` und `pacman-conf.txt`. Falls Keyring fehlt → zuerst diesen installieren.

2. **Distro-spezifische Pakete** (siehe `<distro>-layer/<distro>-packages-installed.txt`) kommen aus dem Distro-eigenen Repo. Bei einem reinen Arch-Setup muss das Repo erst hinzugefügt werden, oder du nimmst ein Distro-ISO als Basis.

3. **Distro's Tweak-Layer** (`/usr/lib/<distro>/`, `/usr/bin/<distro>-*`, Master-Hook) lebt in den Distro-Metapaketen — wird automatisch mitinstalliert, wenn die Pakete aus obiger Liste gezogen werden. Manuell kopieren ist NICHT nötig.

4. **WM-Config ist NUR user-spezifisch** (`~/.config/<wm>/config`), `/etc/skel/` ist meist leer. Bei Mehrbenutzersystemen: manuell in `/etc/skel/.config/<wm>/` kopieren, dann haben neue User die Config sofort.

5. **Systemd-User-Services**: die meisten sind projekt-spezifisch (mazemaker, hermes, btquant, etc.). Bei einem Restore MUSS geprüft werden, welche Projekte tatsächlich gewollt sind — nicht alles blind reaktivieren.

## Snapshot-Datum

Erstellt: <YYYY-MM-DD>
Kernel bei Erstellung: siehe `system-info/kernel.txt`
Paketanzahl bei Erstellung: <T> total, <N> offiziell, <M> AUR, <K> explizit