---
name: remainder-brand-strategy
description: REMAINDER/ANOMALY brand architecture, Matrix references, domain purchasing decision framework, and product naming.
tags: [brand, matrix, domain, naming, anomaly, remainder]
related_skills: [pulse-cloud-api-integration]
---

# REMAINDER Brand Architecture

## The Matrix Reference

**"The remainder of an unbalanced equation"** — The Architect in The Matrix Reloaded.

The equation is balanced — mathematical precision, harmony. Six times destroyed. The anomaly that cannot be eliminated = human choice, human voices.

This is exactly what PULSE does: find the anomalous voices that the equation (algorithmic feed) excludes.

## Brand Names

| Name | Matrix Reference | Product |
|------|-----------------|---------|
| **ANOMALY** | "The eventuality of an anomaly" | Search/API layer (pulse-cloud successor) |
| **REMAINDER** | "The remainder of an unbalanced equation" | Memory/persistence layer (neural-memory successor) |
| **The Architect** | The one who rebuilds the equation | The agent itself (Hermes) |

## Domain Decisions

### REMAINDER domains purchased
- **remainder.online** — €5.04/12mo — PRIMARY (bought)
- remainder.cloud — €3.96/12mo
- remainder.site — €3.00/12mo
- remainder.life — (check price)

### ANOMALY domains to check
- anomaly.systems — €33/12mo (expensive but on-brand)
- anomaly.ai — likely taken, €60-100+/year
- anomaly.io — likely taken, €35-50/year
- anomaly.dev — ~€10-15/year (check)
- anomaly.co — cheaper alternative

### Recommendation
1. **remainder.online** — buy NOW (€5.04, no-brainer)
2. **anomaly.systems** — if Matrix branding matters (€33/year is fine for business)
3. Or just use **remainder.online** as primary brand — name is strong enough on its own

## Architecture

```
ANOMALY.SYSTEMS (or REMAINDER.ONLINE)
├── Anomaly Search     — Social Intelligence API (pulse-cloud)
│   └── "Find what the equation excludes"
├── Remainder Memory   — Neural Semantic Memory (neural-memory)
│   └── "The remainder of an unbalanced equation"
└── (The Architect — the agent itself)
```

## Landing Page

remainder.online serves:
- Full Matrix-branded landing page
- Live PULSE demo with clusters, sources, scoring
- Docs, pricing sections
- CRT scanlines, neural canvas background, glitch text
- "ANOMALY DETECTED — 18+ SOURCES ACTIVE" status line
- Tagline: "The remainder of an unbalanced equation. Find what the noise excludes."

## VM Setup

- Public IP: 91.55.216.166:2222 (SSH)
- Private: 10.0.2.15 (NAT)
- ISP blocks 80/443 → **Cloudflare Tunnel required**
- See skill: `cloudflare-tunnel-vm-deploy`
