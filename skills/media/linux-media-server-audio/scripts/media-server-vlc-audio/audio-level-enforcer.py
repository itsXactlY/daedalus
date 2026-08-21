#!/usr/bin/env python3
"""Audio Level Enforcer for VLC/Jellyfin - Fixed -2.0dB Volume"""

import subprocess
import sys
import time

def get_sinks():
    result = subprocess.run(['pactl', 'list', 'short', 'sinks'], 
                          capture_output=True, text=True)
    return result.stdout.strip().split('\n') if result.stdout.strip() else []

def set_volume(sink_id, percent=80):
    vol_hex = int(percent * 0x10000 / 100)
    subprocess.run(['pactl', 'set-sink-volume', sink_id, f"{vol_hex:#x}"],
                   capture_output=True)

def enforce():
    while True:
        for sink in get_sinks():
            if sink:
                sink_id = sink.split('\t')[0]
                set_volume(sink_id, 80)
        time.sleep(5)

if __name__ == '__main__':
    if '--daemon' in sys.argv:
        enforce()
    else:
        for sink in get_sinks():
            if sink:
                sink_id = sink.split('\t')[0]
                set_volume(sink_id, 80)
        print("Audio levels set to 80%")