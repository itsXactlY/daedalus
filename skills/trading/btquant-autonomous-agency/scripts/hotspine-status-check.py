#!/usr/bin/env python3
"""
HotSpine Status Checker for BTQuant
Checks shared memory, cache, and reports operational state.

Usage: python3 skills/trading/btquant-autonomous-agency/scripts/hotspine-status-check.py
"""
import subprocess
import os
import sys
from pathlib import Path

def check_shm():
    """Check if HotSpine shared memory exists."""
    result = subprocess.run(
        ['ls', '-la', '/dev/shm/BTQ'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return "LIVE", result.stdout.strip()
    return "OFFLINE", "Shared memory /dev/shm/BTQ not found"

def check_cache():
    """Check cache staleness."""
    cache_dir = Path.home() / 'projects/PubBTQuant/.btq_cache'
    if not cache_dir.exists():
        return "MISSING", "No cache directory"
    
    parquet_files = list(cache_dir.glob('*.parquet'))
    if not parquet_files:
        return "EMPTY", "No parquet files in cache"
    
    # Get most recent file
    newest = max(parquet_files, key=lambda p: p.stat().st_mtime)
    mtime = newest.stat().st_mtime
    age_days = (os.path.getmtime(newest) - os.path.getctime(newest)) / 86400
    
    return "STALE", f"{newest.name} ({mtime})"

def check_market_collector():
    """Check if market_data_collector process is running."""
    result = subprocess.run(
        ['pgrep', '-f', 'market_data_collector'],
        capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        return "RUNNING", f"PIDs: {result.stdout.strip()}"
    return "STOPPED", "No market_data_collector process found"

def main():
    shm_status, shm_detail = check_shm()
    cache_status, cache_detail = check_cache()
    collector_status, collector_detail = check_market_collector()
    
    print("=== HotSpine Status Check ===")
    print(f"Shared Memory: {shm_status} - {shm_detail}")
    print(f"Cache: {cache_status} - {cache_detail}")
    print(f"Collector: {collector_status} - {collector_detail}")
    
    if shm_status == "OFFLINE":
        print("\n⚠️  HotSpine OFFLINE - no live trading signals available")
        print("   Restart: cd ~/projects/PubBTQuant && python3 mcp-adapter/tools/build.py build_run --project ccapi --target market_data_collector")
        sys.exit(1)
    else:
        print("\n✅ HotSpine LIVE - trading detectors operational")
        sys.exit(0)

if __name__ == "__main__":
    main()