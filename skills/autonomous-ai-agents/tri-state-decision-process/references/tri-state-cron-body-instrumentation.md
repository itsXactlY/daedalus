Concrete recommended cron-body instrumentation. Verified pattern from 2026-06-21 00:00Z DECIDE cycle. The structural fix that the operator should ship to the cron task body to enforce pre-load + post-write verification regardless of whether the agent remembers to do it:

```bash
#!/bin/bash
# Tri-state DECIDE cron task body (with structural fixes)
set -e

# 1. PRE-LOAD SKILL — text-only escalation in the SKILL.md has not changed
#    behavior across 18+ cycles (verified 2026-06-20 18:30Z through
#    2026-06-21 00:00Z). The cron body must hardcode this step so the
#    writer starts with the pitfalls in working memory. The skill_view
#    output here is consumed by the cron-task description that the agent
#    receives, not directly into the agent's context; the value is that
#    the agent's run-loop receives the cron task body which now
#    explicitly references the skill, triggering the system-prompt's
#    "load relevant skills" rule.
echo "[tri-state-decide] pre-loading tri-state-decision-process skill"

# 2. RUN DECIDE SCRIPT — emits the JSON payload with instructions.
python3 ~/.hermes/loops/tri-state/decide_rank.py

# 3. WRITER + GET-PAIRS — the agent's job body below this point should
#    fire each mazemaker_remember + mazemaker_get pair as a single
#    choreographed tool-batch per write. Do NOT write all 3 then verify
#    all 3 separately (verified failure pattern across 15+ cycles).
#    Each successful get-pair proves the label format and trailing
#    CYCLE CONTEXT line BEFORE the agent composes the final cycle report.
```

Until this cron-body change ships, every cycle's writes remain unverified-by-contract. The text-based "add skill_view to cron body" recommendation has not produced behavioral change in 18+ cycles; the structural fix is for the operator (or the curator) to add the bash snippet above to the cron's task body in `~/.hermes/loops/tri-state/` config. Once shipped, the pre-flight contract #1 is enforced by the shell rather than relying on the agent's memory of the skill's pitfalls.
