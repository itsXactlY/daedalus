#!/usr/bin/env python3
"""Auto-enrichment for Pulse-Wurm discoveries.
Runs after pulse-wurm-2 tick to create linked fact:* and decision:* entries.
See SKILL.md for documentation.
"""
import re
import json
import hashlib
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def hash_string(s: str, length: int = 6) -> str:
    """Create consistent short hash from string."""
    return hashlib.md5(s.encode()).hexdigest()[:length]

def extract_topic_from_content(content: str) -> str:
    """Extract topic from discovery content."""
    # Try multiple patterns
    patterns = [
        r"Topic:\s*(.+?)(?:\n|$)",
        r"discovery topic:\s*(.+?)(?:\n|$)",
        r"seed topic:\s*(.+?)(?:\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    # Fallback: extract first 50 chars of content as topic
    return content[:50].strip()

def extract_url_from_content(content: str) -> str:
    """Extract URL from discovery content."""
    url_pattern = r'https?://[^\s\'"<>\\]+'
    matches = re.findall(url_pattern, content)
    return matches[0].rstrip('\\') if matches else ""

def extract_summary_from_content(content: str) -> str:
    """Extract key finding summary from discovery content."""
    # Look for Key finding / finding / summary patterns
    patterns = [
        r"Key finding:\s*(.+?)(?:\n\n|\n-|$)",
        r"Finding:\s*(.+?)(?:\n\n|\n-|$)",
        r"Summary:\s*(.+?)(?:\n\n|\n-|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            summary = match.group(1).strip()[:200]  # Limit to 200 chars
            return summary
    # Fallback: take first meaningful line
    lines = [l for l in content.split('\n') if l.strip() and not l.startswith('discovery:') and not l.startswith('Topic:') and not l.startswith('Key')]
    return lines[0][:200] if lines else "Discovery recorded"

def create_fact_entry(topic: str, url: str, summary: str, source_seed: str = None) -> dict:
    """Create fact memory entry from discovery."""
    return {
        "label": f"fact:pulse-discovered-{hash_string(topic)}",
        "content": f"{summary}\n\nSource: {url}\n\nThis insight emerged from Pulse-Wurm reconnaissance on '{topic}'.\n\nSalience: High - actionable knowledge for Hermes workflows.",
        "salience": 0.6,
        "linked_from": "pulse-wurm-auto-enrichment"
    }

def create_decision_entry(topic: str, url: str, discovery_id: int) -> dict:
    """Create decision memory entry from discovery."""
    actions = []
    if "github" in url:
        actions.append(f"- Clone and analyze repository for {topic} implementation patterns")
    if "autonomous" in topic.lower() or "agent" in topic.lower():
        actions.append(f"- Evaluate {topic} for integration into autonomous agent workflows")
    if "mcp" in topic.lower() or "protocol" in topic.lower():
        actions.append(f"- Research {topic} compatibility with existing MCP infrastructure")
    
    action_list = "\n".join(actions) if actions else f"- Investigate {topic} for potential workflow integration"
    
    return {
        "label": f"decision:pulse-wurm-action-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}-{hash_string(topic)}",
        "content": f"Action: Evaluate integrating '{topic}' into Hermes workflows.\n\nWhy it matters: Pulse-Wurm reconnaissance identified this as novel and relevant.\n\nSuggested next steps:\n{action_list}\n\nSource discovery ID: {discovery_id}",
        "salience": 0.5,
        "linked_from": "pulse-wurm-auto-enrichment"
    }

def main():
    """Main enrichment function - to be called after pulse-wurm-2 tick."""
    # NOTE: In actual implementation, this would use the mcp_mazemaker tools
    # For cron execution, we write to a temp file that the tick script processes
    
    print("Pulse-Wurm Auto-Enrichment ready")
    print("Call enrich_discoveries() after pulse tick completes with discovery outputs")
    return {"status": "ready", "script_path": __file__}

if __name__ == "__main__":
    main()