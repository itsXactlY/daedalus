---
name: dayz-server-config-system
description: JSON-based server config system - admin lists, RPC, tier management
category: dayz-mod-development
version: 1.0
tags: [dayz, server, config, json, rpc, admin]
---

# DayZ Server Config System

## JSON-Based Admin List Pattern
Full VPPAdminList singleton with Load/Save/IsAdmin/AddAdmin/RemoveAdmin.

## super.OnRPC() Consumption
MUST handle custom RPCs BEFORE calling super to avoid corrupted ctx.
If you call super first, ctx gets consumed and your reads return garbage.

## Settings Serialization
- `WriteToCtx`/`ReadFromCtx` pattern for RPC round-trip
- Field order MUST match between write and read
- Sub-array RPC serialization is tricky

## Config Classes
- JSON-backed config with `Load`/`Save` methods
- $profile paths for persistence
- Dynamic tier reloading from config

## Removed/Corrected
- `GetGame().GetAdmins()` does NOT exist
- Hardcoded Steam IDs are wrong
- `VPPClanTierDef` -> correct name is `VPPClanTier`

## Pitfalls
- Layout<->code widget name mismatches
- Field order must match between Write/Read
- $profile paths
- Sub-array RPC serialization
