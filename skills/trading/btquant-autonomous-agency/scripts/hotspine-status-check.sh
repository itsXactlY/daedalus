#!/usr/bin/env python3
"""HotSpine SHM Status Checker - run before pulse analysis to verify live data availability."""
import os
import subprocess
import json

def check_hotspine_status():
    """Check HotSpine shared memory and return status dict."""
    shm_path = "/dev/shm/BTQ"
    shm_exists = os.path.exists(shm_path)
    
    # Check for market_data_collector process
    try:
        result = subprocess.run(
            ["ps", "aux"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        collector_running = "market_data_collector" in result.stdout
    except Exception:
        collector_running = False
    
    # Check parquet cache for last-known data
    cache_path = "~/projects/PubBTQuant/.btq_cache"
    cache_exists = os.path.exists(os.path.expanduser(cache_path))
    
    status = {
        "hotspine_shm": {
            "exists": shm_exists,
            "path": shm_path
        },
        "market_data_collector": {
            "running": collector_running
        },
        "cache": {
            "exists": cache_exists,
            "path": cache_path
        }
    }
    
    # Print concise status
    if shm_exists and collector_running:
        print("✅ HotSpine LIVE - real-time signals available")
    elif cache_exists and not shm_exists:
        print("⚠️ HotSpine OFFLINE - using stale cache only")
    else:
        print("❌ HotSpine OFFLINE - no cache, no live feed")
    
    return status

if __name__ == "__main__":
    status = check_hotspine_status()
    # Output JSON for programmatic use
    print("\n---JSON---")
    print(json.dumps(status, indent=2))