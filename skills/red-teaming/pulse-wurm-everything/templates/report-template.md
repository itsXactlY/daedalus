# Pulse Recon Tick Report Template

```markdown
# PULSE WURM RECONNAISSANCE REPORT
*Tick executed: {{TIMESTAMP}}*

---

## TOP-10 MOST INTERESTING THINGS FOUND

### 1. **[Topic Title]**
- **What**: Brief description of finding
- **Why it matters**: Impact/why it's significant
- **Source**: Direct URL with engagement stats
- **Category**: [security|ai|science|legal|finance|infrastructure]

### 2. **[...] ... (repeat for 10 items)**

---

## NEW TOPICS DISCOVERED FOR NEXT TICK (N)

1. **[Specific topic name]** - [Brief context]
2. **[...] ... (extract 10-15 items)**

---

## TECHNICAL NOTES

- **Tool status**: [working/timing out/recovery mode]
- **Sources accessed**: [count]/[total] (e.g., 18/23)
- **Deep job status**: [job_ids and states]
- **Any workarounds applied**: [MCP timeout handling, etc.]
```

## Report Assembly Workflow

1. Collect all `pulse_search` results into unified candidate list
2. Sort by engagement_score × source_quality × freshness
3. Extract top 10 with highest combined scores
4. De-duplicate URLs and titles across sources
5. Synthesize key findings focusing on concrete events (not generic papers)
6. Identify 10-15 new specific topics for next tick
7. Update `~/.hermes/pulse-wurm-next-topics.json` with discovered topics