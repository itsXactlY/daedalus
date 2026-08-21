# Deployment to tpad (ThinkPad at 192.168.0.242)

SSH config exists in `~/.ssh/config`:
```
Host tpad
  HostName 192.168.0.242
  User alca
```

## Target setup

- **OS**: Arch Linux
- **Audio system**: PipeWire (not Pulseaudio)
- **Existing services**: mazemaker-pod, pipewire, jellyfin
- **Config location**: `~/.config/jellyfin/system.xml` (user config dir)

## Audio ports/sinks on tpad

Primary sink: `alsa_output.pci-0000_00_1f.3.analog-stereo`

## Commands

```bash
# Copy wrapper and enforcer
scp ~/hermes-skills/media/linux-media-server-audio/templates/vlc-fixed-audio-wrapper.sh tpad:~/bin/vlc-fixed-audio
scp ~/hermes-skills/media/linux-media-server-audio/scripts/audio-level-enforcer.py tpad:~/.local/bin/

# Enable services
ssh tpad '
    chmod +x ~/bin/vlc-fixed-audio ~/.local/bin/audio-level-enforcer.py
    systemctl --user daemon-reload
    systemctl --user enable --now audio-enforcer.service
'
```