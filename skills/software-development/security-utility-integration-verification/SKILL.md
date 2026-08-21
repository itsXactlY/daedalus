---
name: security-utility-integration-verification
description: Verify security utilities are actually wired into production code paths, not just implemented as standalone functions
---

# Security Utility Integration Verification Skill

## When to Use
When implementing security features (padding, masking, timing randomization, etc.) as utilities in a codebase that also has a production code path that MUST use them.

## The Trap
Subagents (and sometimes even direct implementation) implement a security feature as a standalone utility function but forget to wire it into the actual send/encrypt/store/response path. The utility exists, tests pass, but the actual traffic is never protected.

## The Pattern
```python
# Security utility exists
def _pad_payload(data: bytes) -> bytes:
    if not METADATA_PAD_ENABLED:
        return data
    ...

# But is it CALLED in the real send path?
# grep for: encrypt_message, send_message, await ws.send, self.message_relay.send
```

## Anti-Pattern
```python
# Created utility
def _pad_payload(data: bytes) -> bytes:
    ...
    
# But nobody calls it! The real path is:
encrypted = encrypt_message(text, shared_secret)
# ← MISSING: padding here!
self.message_relay.send(sender_id, recipient_id, encrypted, msg_id)
```

## Correct Pattern
After implementing any security utility, you MUST verify integration at every call site in the real send path:
1. Find all places the protected operation happens: `grep -n "encrypt_message\|send_message\|await ws.send"`
2. Check if the security utility is called after each operation
3. If not, integrate it
4. Verify: enable the feature flag and confirm behavior changes

## Lessons from JRWL Messenger (2026-04-24)
- SEC-04 metadata padding was implemented as `_pad_payload()` utility
- BUT it was NOT called in the WS message send path (2 call sites for 1:1, 1 for group)
- Had to add to BOTH the direct message path AND the group message loop
- Same for random delay — implemented but not in the actual dispatch path

## Verification Checklist
- [ ] Security utility exists
- [ ] Utility is called at EVERY real traffic point (not just test paths)
- [ ] Feature flag controls it (paranoid mode = off by default)
- [ ] Enabling the flag actually changes observable behavior
- [ ] Tests verify the integration point, not just the utility in isolation
