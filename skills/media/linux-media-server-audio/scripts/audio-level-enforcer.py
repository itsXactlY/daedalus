#!/usr/bin/env python3
import subprocess
import time
import sys

def get_sinks():
    result = subprocess.run(['pactl', 'list', 'short', 'sinks'], 
                          capture_output=True, text=True)
    return result.stdout.strip().split('\n') if result.stdout.strip() else []

def set_fixed_volume(sink_id, volume_percent=80):
    vol_hex = int(volume_percent * 0x10000 / 100)
    subprocess.run(['pactl', 'set-sink-volume', sink_id, f"{vol_hex:#x}"],
                   capture_output=True)

def main():
    print("Audio Level Enforcer running (target: -2.0dB / 80%)")
    while True:
        for sink in get_sinks():
            if sink:
                sink_id = sink.split('\t')[0]
                set_fixed_volume(sink_id, 80)
        time.sleep(5)

if __name__ == '__main__':
    if '--daemon' in sys.argv:
        main()
    else:
        for sink in get_sinks():
            if sink:
                sink_id = sink.split('\t')[0]
                set_fixed_volume(sink_id, 80)
        print("Audio levels set to 80%")