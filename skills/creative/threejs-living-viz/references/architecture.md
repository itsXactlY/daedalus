# Dream Stream / Maze Cosmos — Architecture Reference

Built 2026-05-21 for the mazemaker-architect project at `~/projects/mazemaker-architect/public/`.

## File Manifest

| File | Lines | Size | Role |
|------|-------|------|------|
| `dream-stream.html` | 1056 | 44K | Fullscreen 24/7 livestream. No UI chrome. THE viral one. |
| `maze-cosmos.html` | 529 | 28K | 3D galaxy v2: constellations, plasma edges, mood, RGB shift |
| `maze-trailer.html` | 288 | 15K | 30-second cinematic trailer. 4 acts. Camera flythrough. |
| `src/maze-panel.js` | 356 | 16K | Architect dashboard integration. M00 MAZE panel. |

## Dream Stream Architecture

### Data Flow
1. `fetchWonderland()` → health check on `127.0.0.1:8765`
2. If reachable: fetch `mazemaker_stats` (via MCP), `memory/list?limit=300`, per-node connections
3. If unreachable: generate synthetic data (200 nodes, 500 edges, labeled clusters)
4. `buildGraph(data)` → create Three.js scene objects
5. `animate()` → render loop with phase/mood/heartbeat

### Scene Structure
- `scene.children`: [stars(Points), nebula(Points), nodeSprites(Points), edgeLines3D(LineSegments), particleSystems(Points×N), labelSprites(Sprite×N)]
- Background: `scene.background` set dynamically per phase

### State Variables
- `nodes` (Array), `edgesData` (Array), `nodeMap` (Map<id,node>)
- `clusterCenters` (Array<{cx,cy,cz,color,name}>)
- `phaseName` (String), `phaseStart` (Number), `phaseProgress` (0-1)
- `mood` (String), `moodTimer` (Number)
- `edgeParticles` (Array<{mesh,pCount,srcIdx,tgtIdx,pos,col,vel,spd,color}>)
- `isLive` (Boolean)

### Phase Durations
- AWAKE: 16000ms, NREM: 24000ms, REM: 14000ms, INSIGHT: 18000ms
- Total cycle: ~72s

### Mood States
'tranquil','inquisitive','turbulent','serene','emerging','ancient','feverish','still'
- Change on phase transition + every ~18-26s within phase
- Colors shift node tint 15% toward mood color

### Edge Colors by Type
- bridge: #76d9ff (cyan)
- causal: #FF8C00 (orange)
- supports: #00FA9A (mint)
- supersedes: #FF4444 (red)
- default: #BF00FF (violet)

### Audio Configuration (dream-stream only)
- AWAKE: 55Hz sine, filter 200Hz, gain 0.04
- NREM: 28Hz sine, filter 100Hz, gain 0.06
- REM: 130Hz triangle, filter 800Hz, gain 0.03
- INSIGHT: 85Hz sine, filter 1500Hz, gain 0.05
- pulseAudio(): 200-600Hz ping, 0.3s decay, fires on REM/Insight transitions

### Keyboard Controls
- Space/P: advance phase manually
- R: toggle autorotation
- F: toggle fullscreen
