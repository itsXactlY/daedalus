---
name: dayz-pbo-build-deploy
description: DayZ mod PBO build, pack, and deploy workflow with toolchain commands
category: dayz-mod-development
tags: [dayz, pbo, build, deploy, toolchain, pboproject]
---

# DayZ PBO Build & Deploy Workflow

## Overview
End-to-end workflow for building DayZ mod PBOs from source, deploying to server, and restarting.

## Directory Structure
```
mods/
  MyMod/
    addons/          # Game data (config.cpp, models, textures)
      config.cpp
    scripts/         # Enforce Script source (.c files)
      3_Game/
      4_World/
      5_Mission/
    mod.cpp          # Mod metadata (name, author, version)
```

## Build Steps

### 1. Pack PBO
```bash
# Using AddonBuilder (DayZ Tools)
AddonBuilder "mods/MyMod/addons" "P:\Mods\@MyMod\addons\MyMod.pbo" -clear

# Using pboproject (batch mode)
pboproject /F="mods/MyMod" /O="output/@MyMod"
```

### 2. Deploy to Server
```bash
cp -r "output/@MyMod" "$SERVER_DIR/mods/@MyMod"
```

### 3. Update Server Config
Add to `serverDZ.cfg` mods list:
```
class Missions { ... mods[]={"@MyMod"}; }
```

### 4. Restart Server
```bash
# Proton/Wine
cd "$SERVER_DIR" && bash restart.sh
```

## Critical Rules

### mod.cpp Must Exist
Without mod.cpp the mod won't load. Required fields:
```
name="MyMod";
author="Author";
```

### config.cpp Class Nesting
Child classes MUST be inside parent class braces:
```
class CfgPatches {
    class MyMod {
        units[]={};
        weapons[]={};
        requiredVersion=0.1;
        requiredAddons[]={"DZ_Data"};
    };
};
```

### Script Compilation Order
Enforce Script compiles by directory order:
- 3_Game/ first (base classes)
- 4_World/ second (entity classes)
- 5_Mission/ last (mission classes)

Reverse order = "undeclared identifier" errors.

## Pitfalls
- AddonBuilder expects P:\ drive mapping (Windows paths)
- Missing requiredAddons causes silent load failure
- PBO must be rebuilt on ANY source change — no incremental
- Check server RPT logs after deploy: `$SERVER_DIR/profiles/*.RPT`
