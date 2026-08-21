---
name: linux-media-server-audio
description: "Configure VLC/Jellyfin on Linux with fixed audio levels, bass boost, and stereo enforcement. Deploy via systemd quadlet on Arch/RHEL systems."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
prerequisites:
  commands: [vlc, pactl, python3, systemctl, scp, ssh]
  packages: [vlc, pulseaudio, pipewire-pulse, lsp-plugins]
---

# Linux Media Server Audio Configuration

Configure VLC/Jellyfin for **fixed audio levels** - no louder/noisier per source. Stereo enforcement. Bass boost.

## When to use this skill

User wants:
- Consistent audio level across ALL media sources (movies, music)
- Bass boost / "Wumms" enhancement
- Stereo enforcement (no multichannel variation)
- Systemd service integration

## Target parameters (user-adjustable)

```yaml
audio_target_db: 0.0        # -2.0dB (quieter) or 0.0dB (lauter)
bass_boost_bands:           # Equalizer bands in Hz:dB format
  - "60Hz:12dB"           # Bass boost - Wumms!
  - "170Hz:8dB"           # Mid-bass
  - "310Hz:6dB"           # Low mids
volume_percent: 100         # 255 = 100%
norm_ratio: 2.0             # Compression ratio (lower = smoother)
```

## Files to create

### 1. VLC wrapper script (`~/bin/vlc-fixed-audio`)

```bash
#!/usr/bin/env bash
VLC_ARGS=(
    --intf dummy --play-and-exit
    --audio-filter="norm{reference=${TARGET_DB}dB}"
    --norm-target=${TARGET_DB}
    --audio-channels=stereo
    --equalizer-bands="${BASS_BANDS}"
    --volume=${VOL_HEX}
    --no-audio-replay-gain --no-audio-time-stretch
)
exec /usr/bin/vlc "${VLC_ARGS[@]}" "$@"
```

### 2. Audio enforcer daemon (`~/.local/bin/audio-level-enforcer.py`)

Python script that continuously clamps pulseaudio sinks to target volume.

### 3. Systemd service (`~/.config/systemd/user/audio-enforcer.service`)

```ini
[Unit]
Description=VLC Audio Level Enforcer
After=pipewire.service
After=jellyfin.service  # Coupled start

[Service]
ExecStart=/usr/bin/python3 ~/.local/bin/audio-level-enforcer.py --daemon

[Install]
WantedBy=jellyfin.service
```

### 4. Jellyfin renderer (`~/.config/jellyfin/renderer/vlc-fixed.xml`)

```xml
<CustomExternalPlayer>
  <Path>~/bin/vlc-fixed-audio</Path>
  <Args>--intf dummy --play-and-exit --audio-filter="norm{reference=0.0dB}" --audio-channels=stereo "{path}"</Args>
  <Name>VLC WUMMS Audio</Name>
</CustomExternalPlayer>
```

## Deployment on target host (tpad)

Via `mosh tpad` or SSH with config in `~/.ssh/config`:

```bash
# Copy files
scp ~/bin/vlc-fixed-audio ~/.local/bin/audio-level-enforcer.py tpad:~/bin/

# Enable systemd services
ssh tpad '
    systemctl --user daemon-reload
    systemctl --user enable --now audio-enforcer.service
    # In Jellyfin Dashboard → Playback → External Players → Enable VLC Fixed Audio
'
```

## Pitfalls

- **mosh/ssh PTY issues**: Commands may need `ssh -t` for TTY-required operations
- **PulseWire vs Pulseaudio**: Use `pactl` for PipeWire systems (tpad uses PipeWire)
- **%h in systemd units**: Expands but can cause path issues - use absolute paths
- **Audio device access**: Containers need `--device /dev/snd` for hardware audio

## Verification

```bash
# Check active sinks
pactl list short sinks

# Test enforcer
python3 ~/.local/bin/audio-level-enforcer.py

# Verify Jellyfin sees renderer
ls ~/.config/jellyfin/renderer/
```

## Companion: VLC fixed-audio service (absorbed from `media-server-vlc-audio`)

The VLC-fixed-volume audio path — a `systemd --user` `audio-enforcer` service that pins
Jellyfin's external-player audio to a fixed level (the `-2.0dB` standard) — was absorbed
from `media-server-vlc-audio`. Its templates/scripts (the enforcer unit, the level script,
the Jellyfin external-player wiring) are re-homed under this skill:

- `templates/media-server-vlc-audio/` — systemd unit + enforcer script templates.
- `scripts/media-server-vlc-audio/` — install/verify helper.

Use these when the operator wants the VLC-fixed-audio variant instead of (or alongside)
the PipeWire/PulseWire enforcer described above.