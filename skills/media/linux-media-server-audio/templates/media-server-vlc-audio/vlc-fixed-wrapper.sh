#!/usr/bin/env bash
exec /usr/bin/vlc --intf dummy --play-and-exit \
    --audio-filter="norm{reference=-2.0dB}" \
    --norm-target=-2.0 \
    --audio-channels=stereo \
    --volume=192 \
    --no-audio-replay-gain \
    --no-audio-time-stretch "$@"