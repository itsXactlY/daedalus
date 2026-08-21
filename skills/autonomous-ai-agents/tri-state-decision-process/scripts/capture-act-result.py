"""Capture the result of a delegated sub-agent task for later audit.

The Tri-State ACT phase delegates implementation work to sub-agents via
delegate_task. Sub-agent summaries are self-reports and may drop detail.
This script writes the JSON payload files produced by the sub-agent into
a durable artifact under ~/.hermes/loops/tri-state/act-artifacts/ so the
orchestrator can audit and reference them on later ticks.

The pattern: orchestrator -> delegate_task(sub-agent) -> sub-agent writes
JSON payload to /tmp/hermes-act-requests/<date>/task-*.json -> orchestrator
reads payload, calls mazemaker_remember, then runs this script to capture
the request files as a numbered artifact.

Usage:
    capture-act-result.py <task-id> <request-dir> <status>

Example:
    capture-act-result.py task-A-20260623 /tmp/hermes-act-requests/20260623 done

Status is one of: done, failed, blocked, partial.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ARTIFACT_ROOT = Path.home() / ".hermes" / "loops" / "tri-state" / "act-artifacts"


def capture(task_id: str, request_dir: str, status: str) -> int:
    src = Path(request_dir)
    if not src.is_dir():
        print(f"error: {src} is not a directory", file=sys.stderr)
        return 2
    dst = ARTIFACT_ROOT / task_id
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in src.iterdir():
        if f.name.startswith("task-"):
            shutil.copy2(f, dst / f.name)
            copied.append(f.name)
    manifest = {
        "task_id": task_id,
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "status": status,
        "request_dir": str(src),
        "files_copied": sorted(copied),
    }
    (dst / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Captured {len(copied)} files to {dst} (status={status})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(capture(*sys.argv[1:]))
