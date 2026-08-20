---
name: parallel-code-audit-crew
description: Deep codebase audit using parallel sub-agent crews — structural analysis, thread safety, logic bugs, and crypto correctness in a single coordinated pass
category: software-development
---

# Parallel Code Audit Crew — Methodology

## When to Use
When asked to do a deep line-by-line, function-by-function review of a large, complex codebase. Use this crew-based parallel approach instead of reviewing sequentially — it's 4-6x faster and produces better results because each agent goes deeper on their domain.

## Core Principle
**Read files first, then delegate in parallel.** Each sub-agent focuses exclusively on their concern domain and reads the full codebase independently (don't pre-digest for them — they need the full context).

## Audit Domain Matrix
Split the audit across 4 parallel tracks:

| Agent | Focus Areas |
|-------|-------------|
| **Agent 1: Thread Safety** | Race conditions, lock coverage, data races, concurrent access patterns, lock ordering |
| **Agent 2: Logic & Architecture** | API logic bugs, state machine correctness, edge cases, null handling, boundary conditions |
| **Agent 3: Security & Crypto** | Crypto spec compliance, auth bypasses, input validation, injection, information disclosure |
| **Agent 4: Integration & Data** | DLM/persistence races, recovery bugs, index inconsistencies, schema edge cases |

## Step-by-Step Execution

### Phase 1: Reconnaissance (do first)
```bash
# Get file inventory and line counts
find /path/to/project -name "*.py" | sort
wc -l /path/to/project/*.py

# Read the largest/most complex files in full before delegating
# This lets you design the audit domains intelligently
```

### Phase 2: Parallel Crew Dispatch
Use `delegate_task` with `tasks=[]` (batch mode) to run all agents simultaneously.

**CRITICAL**: Pass the following to EVERY sub-agent:
- The full file paths
- The full file contents (read_file in the sub-agent context)
- Explicit instruction to report EVERY issue with exact line numbers and code snippets

**Template for each agent:**
```
Audit [file] for [domain]. Read the full file (~[N] lines).
Check:
1. [domain-specific checklist]
2. [domain-specific checklist]
Report EVERY issue found with exact line numbers and code snippets.
```

### Phase 3: Synthesis
Collect all results. Build a unified bug table:

| ID | Category | Severity | Location | Bug | Fix |
|----|----------|----------|----------|-----|-----|

## Domain-Specific Checklists

### Thread Safety Checklist
- [ ] All state-holding classes have `self._lock = threading.Lock()`
- [ ] Every method that reads/writes shared state acquires the lock
- [ ] Lock is held for the minimum necessary time (snapshot under lock, I/O outside)
- [ ] No dict iteration (`for k in dict.keys()`) without holding the lock
- [ ] No lock-free reads of mutable state that could be concurrently modified
- [ ] `broadcast_to` / `broadcast_all` — WS object could be closed by concurrent `remove()` during iteration
- [ ] `cleanup_*` methods called from background threads need lock coverage
- [ ] TOCTOU patterns: check-then-act across multiple operations

### Logic & Architecture Checklist
- [ ] All API endpoints validate required fields before processing
- [ ] Null/None inputs handled at every layer
- [ ] ID collision handling in creation functions
- [ ] Message deduplication (same msg_id sent twice)
- [ ] Timestamp comparisons (float vs ISO string)
- [ ] String manipulation bugs (replace removes ALL occurrences, not just suffix)
- [ ] Group membership changes invalidating stored/encrypted state
- [ ] Empty collections edge cases
- [ ] OFF-by-one errors in counting/limits

### Security Checklist
- [ ] All crypto operations use spec-compliant parameters
- [ ] Auth/authz checks on every privileged endpoint
- [ ] Input validation before crypto operations
- [ ] No private key material in API responses
- [ ] Rate limiting on sensitive endpoints
- [ ] XSS/Injection in message content paths
- [ ] CORS configuration for browser clients
- [ ] WebSocket authentication (challenge-response or equivalent)
- [ ] Failed verification not falling through to success path

### Crypto Checklist
- [ ] X3DH: DH operations use correct coordinate (x-only vs x||y)
- [ ] AES-GCM nonce length = 12 bytes (NIST standard)
- [ ] ECDSA uses fips-186-3 + SHA-256
- [ ] Double Ratchet: skipped keys checked AFTER the loop, not inside
- [ ] Ratchet state: load+save race between threads/processes
- [ ] Safety numbers: byte ordering is canonical
- [ ] Prekey consumption: atomic consume-and-delete

## Critical Bug Patterns (Top 10)
1. **Lock-free dict iteration** → `RuntimeError: dictionary changed size during iteration`
2. **Replace-all instead of replace-suffix** → `str.replace('_s', '')` removes ALL occurrences
3. **TOCTOU in DLM/persistence** → Read state, modify, blind-write (loses concurrent changes)
4. **Fallback on parse failure** → Silent default masks corrupt data forever
5. **No auth on sensitive endpoint** → Anyone can consume OPKs / retrieve bundles
6. **Verification failure not blocking** → Fall-through allows malicious actors
7. **WS object closed during broadcast** → Silent message drop
8. **Ratchet load+save race** → Last-write-wins loses message keys
9. **Group roster changes break stored ciphertext** → Key tied to dynamic state
10. **DKL registry blind overwrite** → Lost writes in concurrent scenarios

## Output Format
Each sub-agent should report in this structure:
```
## [Domain] Audit

### ISSUE N: [Short Title]
**Lines**: [exact]
**Severity**: CRITICAL/HIGH/MEDIUM/LOW
**File**: [path]
**Code**:
```python
[exact code]
```
**Bug**: [explanation]
**Fix**: [recommended approach]
```

## Tips
- Sub-agents have NO memory of your conversation — pass everything in context
- Give each agent a distinct focus to avoid overlap and redundant work
- Request code snippets with exact line numbers for every issue
- Instruct agents to report EVEN the low-severity issues — they compound
- After synthesis, sort by severity: CRITICAL first, then work through HIGH → MEDIUM → LOW
