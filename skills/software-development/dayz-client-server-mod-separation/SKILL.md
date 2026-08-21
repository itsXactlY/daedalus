---
name: dayz-client-server-mod-separation
description: Patterns for DayZ client/server mod architecture — separating handlers, preventing RPC duplication, understanding missionServer.c dual-runtime behavior
category: software-development
---

# DayZ Client/Server Mod Separation

## Core Pattern
Two mods in this architecture:
- **VanillaPPMap** (client mod) — UI, markers, user-facing features
- **VanillaPPMap_Server** (server mod) — group management, server-side state

## Critical Rule: missionServer.c Runs on BOTH
`missionServer.c` executes on the server for ALL connected players. Adding server-side handlers (like GROUP_CREATE) to the client mod's missionServer.c creates **duplicate handlers** — both fire on the server.

## Symptoms of Duplicate Handlers
- "String CORRUPTED - FIX OnStoreLoad()" errors
- `ctx.Read(tag)` fails because first handler consumed the ctx buffer
- Error at line where `ParamsReadContext.Read()` is called

## RPC Routing Chain
```
Client RPC → DayZGame.OnRPC → VanillaPlusPlus.OnRPC (client mod)
    ↓ (if GROUP_RPC_MIN <= rpc <= GROUP_RPC_MAX)
VPPRPCManager.OnRPC → registered handler (GroupServerManager)
```

## What Goes Where

| Component | Client Mod (VanillaPPMap) | Server Mod (VanillaPPMap_Server) |
|-----------|--------------------------|----------------------------------|
| missionServer.c | Only marker RPCs (GetRPCManager) | N/A — no missionServer.c |
| Group RPCs | UI sends via ScriptRPC | GroupServerManager handles |
| VPPRPCManager | Routes to VPPGroupRPCs | N/A — client mod provides |
| Chat/VPPChatManager | Client UI | Server-side state |

## Anti-Patterns
1. ❌ Adding GROUP_CREATE/etc handlers to client mod's missionServer.c
2. ❌ Assuming server mod has its own VPPRPCManager (uses client mod's)
3. ❌ Not clearing compiled script cache after reverting missionServer.c

## RPC Override Order: super.OnRPC() Causes ctx Corruption

When overriding `OnRPC` (e.g., `VanillaPlusPlus.OnRPC`), calling `super.OnRPC()` BEFORE your handler **consumes/corrupts `ParamsReadContext`** data.

**Bad (ctx consumed by super before VPP reads it):**
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    super.OnRPC(sender, target, rpc_type, ctx); // ← ctx may be consumed here
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx); // ← reads corrupted ctx
    }
}
```

**Fix (route VPP RPCs before super, then return):**
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
        return; // ← skip super for VPP-managed RPCs
    }
    super.OnRPC(sender, target, rpc_type, ctx); // ← non-VPP RPCs still get base handling
}
```

**Rule:** If your mod manages its own RPC range, intercept BEFORE calling super. The `return` prevents the base class from touching data your handler needs.

## Fix: Compiled Cache
If String CORRUPTED persists after source revert:
1. Stop server completely
2. Delete `storage_x/` in server profile
3. Delete `.c.cache` files in `mpmissions/`
4. Restart — server recompiles from source

## Debug Check
Look for this in server logs:
```
[VPPGroups] Server-side group handlers registered.
```
If present, your client mod's missionServer.c still has old group code in compiled cache.
