---
name: dayz-mod-merge-workflow
description: Workflow for merging complementary DayZ mods (e.g. VPPMaps + Colorful-UI-Pro) with no direct duplicates
category: dayz-mod-development
---

# DayZ Mod Merge Workflow

## Overview

This workflow covers merging complementary DayZ mods that have no direct file duplicates. Example case: VPPMaps + Colorful-UI-Pro.

## Pre-Merge Analysis

### Check for Duplicates
- Compare file lists between both mods
- Verify no identical filenames in same paths
- Identify complementary features (what each mod contributes)

### Map Source Paths
DayZ mods often have files in multiple locations:
- **Client scripts:** Usually in a client-specific directory
- **Server scripts:** Usually in a server-specific directory
- **Shared resources:** config.cpp, textures, models

## Merge Process

### Step 1: Copy from Multiple Source Paths

```bash
# Copy client scripts from Mod A
cp -r /path/to/modA/client/* /path/to/merged/

# Copy server scripts from Mod A
cp -r /path/to/modA/server/* /path/to/merged/

# Copy client scripts from Mod B
cp -r /path/to/modB/client/* /path/to/merged/

# Copy server scripts from Mod B
cp -r /path/to/modB/server/* /path/to/merged/
```

### Step 2: Merge config.cpp

Combine input bindings from both mods into a single config.cpp:
- Keep all input action definitions from both mods
- Ensure no duplicate action names
- Combine UI class definitions
- Merge any shared config sections

### Step 3: Create Build + Start Script

Create a unified script matching your existing workflow:
```bash
#!/bin/bash
# Build merged mod PBO
pboproject "merged_source" "merged_output.pbo"

# Deploy to server
cp merged_output.pbo /path/to/server/mods/

# Start server
./start_server.sh
```

## Key Principles

1. **Verify complementary nature** - ensure mods don't overwrite each other
2. **Preserve all input bindings** - merge, don't replace
3. **Test after merge** - verify both mod features work
4. **Maintain build workflow** - use positional args for PBO building (see dayz-pbo-build-workflow skill)

## Pitfalls

- Don't assume mods are compatible without checking file lists
- config.cpp merges need careful attention to class nesting
- Always test both sets of functionality after merging
