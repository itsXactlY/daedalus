---
name: dayz-rpc-communication
description: DayZ client-server RPC communication patterns using VPPRPCManager
category: dayz-mod-development
tags: [dayz, rpc, client-server, networking, vpp, communication]
---

# DayZ RPC Communication Patterns

## Overview
DayZ mods communicate between client and server via ScriptRPC. VPPRPCManager provides a typed handler registry on top of DayZ's raw RPC system.

## Architecture

### RPC ID Ranges
Each mod subsystem owns a range of RPC IDs to avoid collisions:
```
GROUP_RPC_MIN   = 500
GROUP_RPC_MAX   = 509
SETTINGS_RPC    = 510
MARKER_RPC_MIN  = 520
MARKER_RPC_MAX  = 529
```

### Registration (Client)
```cpp
VPPRPCManager rpc = VPPRPCManager.Get();
rpc.RegisterRPC(VPPGroupRPCs.GROUP_SYNC_DATA, ScriptCaller.Create(OnGroupDataReceived));
rpc.RegisterRPC(VPPGroupRPCs.GROUP_INVITE_RECEIVED, ScriptCaller.Create(OnInviteReceived));
```

### Dispatch (DayZGame)
```cpp
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    super.OnRPC(sender, target, rpc_type, ctx);
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
    }
}
```

## Client -> Server Pattern

### Send
```cpp
ScriptRPC rpc = new ScriptRPC();
rpc.Write(playerId);
rpc.Write(settingValue);
rpc.Send(null, VPPSettingsRPCs.SAVE_SETTING, true, null);
```

### Receive (Server)
```cpp
void OnSaveSetting(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    Param2<string, float> data;
    if (!ctx.Read(data)) return;

    string playerId = data.param1;
    float value = data.param2;

    // Validate
    if (value < 0.0 || value > 1.0) return;

    // Persist
    SavePlayerSetting(playerId, value);

    // Acknowledge
    SendAck(sender, rpc_type);
}
```

## Server -> Client Pattern

### Send (Server)
```cpp
void SendToClient(PlayerIdentity identity, int rpcId) {
    ScriptRPC rpc = new ScriptRPC();
    rpc.Write(m_CachedData);
    rpc.Send(null, rpcId, true, identity);
}
```

### Receive (Client)
```cpp
void OnDataReceived(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    Param1<ref MyData> data;
    if (!ctx.Read(data)) return;

    m_LocalData = data.param1;
    RefreshUI();
}
```

## Critical Rules

### Always Null-Check Identity
```cpp
if (!identity) return;  // NULL on reconnect, BBP edge cases
```

### Register Before First Possible RPC
Handlers registered AFTER the RPC arrives are silently dropped. Register in constructor or `OnInit()`.

### Use Delayed Request (Client -> Server)
Don't request data immediately on connect — server may not be ready:
```cpp
GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(RequestData, 12000, false);
```

### Param Types Must Match
Client writes `Param2<string, float>` — server must read `Param2<string, float>`. Mismatch = silent read failure.

## Pitfalls
- RPC handlers defined but NEVER registered = handlers exist but never fire
- OnClientReadyEvent override crashes all connections silently — use InvokeOnConnect
- Race condition: server loads data at 10s -> client must request AFTER 10s (use 12s+)
- No error feedback on failed ctx.Read() — always check return value
