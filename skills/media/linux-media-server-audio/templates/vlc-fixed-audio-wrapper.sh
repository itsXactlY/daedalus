#!/usr/bin/env bash
# VLC Fixed Audio for Jellyfin - MIT WUMMS & TIEFEN
VLC_WUMMS_ARGS=(
    --intf dummy --play-and-exit
    --audio-filter="norm{reference=0.0dB,soft-knee=0.5,ratio=2.0}"
    --norm-target=0.0 --norm-max-volume=2.0
    --audio-channels=stereo --audio-stereo-mode=1
    --equalizer-bands=60Hz:12dB,170Hz:8dB,310Hz:6dB
    --volume=255 --no-audio-replay-gain --no-audio-time-stretch
)
exec /usr/bin/vlc "${VLC_WUMMS_ARGS[@]}" "$@"