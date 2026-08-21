# V4 Comic Generation — Sector Usecase Reference

Generated 2026-06-08 with sourceful/riverflow-v2.5-pro:free (xhigh reasoning).
115 usecases across 19 sectors. One image per usecase.

## Sector Breakdown

| Sector | Count | IDs |
|--------|-------|-----|
| HEALTHCARE | 10 | health-01 through health-10 |
| MILITARY | 10 | military-01 through military-10 |
| FINANCE | 10 | finance-01 through finance-10 |
| GOVERNMENT | 10 | gov-01 through gov-10 |
| ACADEMIA | 10 | academia-01 through academia-10 |
| CRITICAL INFRASTRUCTURE | 10 | infra-01 through infra-10 |
| ENERGY | 7 | energy-01 through energy-07 |
| SPACE & AEROSPACE | 6 | space-01 through space-06 |
| TELECOM | 5 | telecom-01 through telecom-05 |
| LEGAL | 5 | legal-01 through legal-05 |
| INSURANCE | 4 | insurance-01 through insurance-04 |
| SUPPLY CHAIN | 5 | supply-01 through supply-05 |
| INTELLIGENCE | 4 | intel-01 through intel-04 |
| CLIMATE | 4 | climate-01 through climate-04 |
| CYBERSECURITY | 5 | cyber-01 through cyber-05 |
| MANUFACTURING | 3 | manufacturing-01 through manufacturing-03 |
| TECHNOLOGY | 3 | tech-01 through tech-03 |
| QUANTUM | 2 | quantum-01 through quantum-02 |
| EMERGENCY SERVICES | 2 | emergency-01 through emergency-02 |

## Mazemaker Technologies Referenced Per Usecase

Every scene references at minimum 2-3 of these technologies:

- **Neural Memory Graph** — 3D node-edge network, 1024-d embedding clusters, pulsing connection threads
- **Dream Engine** — 7-phase entity (NREM Loom, REM Forge, Insight Garden, Supercedes Arbiter, Synthesis Alembic, AFE Extractor, DAE Mirror)
- **Rootless Podman Federation** — 4-container pod, peer-to-peer sync arrows, ROOTLESS badge, SHA-256 chain links
- **Post-Quantum Encryption** — Crystal-Dilithium lattice key exchange, AES-256-GCM + ChaCha20 dual shield
- **Zero-Knowledge Protocol** — Lock icon with partial reveal, verify-without-exposing fog
- **PULSE Search** — 22-source fan-out satellite dish array (Reddit, HN, GitHub, YouTube, ArXiv icons)
- **Recall Prism** — Prismatic crystal splitting white light into multicolored memory beams
- **Federation Protocol** — Encrypted tunneled graph exchange between pods

## Generation Parameters

- Model: `sourceful/riverflow-v2.5-pro:free`
- Reasoning: `{effort: "xhigh"}`
- Aspect: 21:9 ultrawide (1536x672)
- Style: Mazemaker hero.webp (teal/pink/charcoal, blueprint grid, manga ohmsha)
- Characters: ARCHITECT, SYSTEM, DREAM ENGINE, INCEPTIONS (same as V3)
- Format: Single-panel comic illustration with dialogue, narration, labels
- Time per image: ~170-200s
- Total estimated: ~5.5-6.5h for 115 images

## Output Structure

```
v4/outputs/
├── healthcare/
│   ├── health-01_hospital_data_federation.webp
│   ├── health-02_genomic_research_privacy.webp
│   └── ...
├── military/
│   ├── military-01_classified_intelligence_mesh.webp
│   └── ...
└── ...
```

## Actual Session Results (2026-06-08)

### First Run (no rate limiting)
- **7 images generated** (health-01 through health-07)
- Ran for 31 minutes before hitting rate limit
- All 7 successful images are 100-400KB webp

### Rate Limit Behaviour
After image 7, every subsequent call returned:
```
{"error": {"message": "Rate limit exceeded: limit_rpm/sourceful/riverflow-v2.5-pro-20260605/..."}}
```
- Model ID `-20260605` suggests a time-limited free tier
- Exponential backoff (30s → 300s max) did NOT help after 47 consecutive retries
- Total retry time: ~3.7 hours with zero additional images
- First image timed out even with minimal prompt (low effort, 1000 tokens)
- Conclusion: free tier has a hard daily cap (~7-10 images)

### Retry Approach Tried
1. Exponential backoff retry script (30s base, 1.5x multiplier, 300s max, jitter) — failed
2. Direct API test with low-effort reasoning — timed out at 120s
3. HuggingFace FLUX.1-schnell free inference — DNS resolution failed (local network issue)
4. OpenRouter paid fallback not attempted (user had free-tier expectation)

### Recommended Fallbacks for Future
- FAL AI: `FAL_KEY` at fal.ai, free credits on signup, `flux/schnell` model
- HuggingFace: `HF_TOKEN` env var, `black-forest-labs/FLUX.1-schnell` free inference
- OpenRouter paid: `google/gemini-3.1-flash-image-preview` (~0.05¢/image)
- OpenRouter paid: `black-forest-labs/FLUX.1-schnell` (~$0.001/image)
