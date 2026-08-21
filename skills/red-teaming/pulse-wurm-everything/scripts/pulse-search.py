#!/usr/bin/env python3
"""
pulse-search.py - Direct REST API search for pulse pod when MCP tools time out.
Use when mcp__pulse__pulse_search or mcp__pulse__pulse_research calls timeout.

Usage:
    python pulse-search.py "quantum computing market" --depth quick --days 30
    python pulse-search.py "open source AI models" --depth default --days 45
"""

import json
import subprocess
import sys
from typing import Optional

def pulse_search(topic: str, depth: str = "quick", lookback_days: int = 90, 
               sources: Optional[str] = None, llm_filter: bool = True,
               n: int = 20) -> dict:
    """Execute pulse search via direct REST API call."""
    
    payload = {
        "topic": topic,
        "depth": depth,
        "lookback_days": lookback_days,
        "llm_filter": llm_filter,
        "n": n
    }
    if sources:
        payload["sources"] = sources.split(",")
    
    cmd = [
        "curl", "-s", "http://127.0.0.1:8770/search",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    
    return json.loads(result.stdout)

def extract_ranked_candidates(data: dict, limit: int = 15) -> list:
    """Extract ranked candidates for report generation."""
    candidates = data.get("ranked_candidates", [])[:limit]
    return [
        {
            "title": c.get("title", "")[:100],
            "url": c.get("url", ""),
            "source": c.get("source", ""),
            "score": c.get("final_score", 0),
            "freshness": c.get("freshness", 0)
        }
        for c in candidates
    ]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pulse-search.py <topic> [--depth quick|default|deep] [--days N]")
        sys.exit(1)
    
    topic = sys.argv[1]
    depth = "quick"
    days = 90
    
    # Parse optional args
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--depth" and i + 1 < len(args):
            depth = args[i + 1]
            i += 2
        elif args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        else:
            i += 1
    
    data = pulse_search(topic, depth, days)
    candidates = extract_ranked_candidates(data)
    
    for c in candidates:
        print(f"- {c['title']}")
        print(f"  Source: {c['source']} | Freshness: {c['freshness']}d")
        print(f"  URL: {c['url']}")
        print()