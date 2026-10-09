# architecture.svg: expert-level system infographic
Status: done
Asked: "yes. then do an properly expert level svg" — of the longterm-agent-work-on-64k-tape infographic
Done when: valid standalone SVG on disk, XML-verified, numbers match this session's measurements

## Steps
- [x] 0. recall prior infographic + verify numbers — mazemaker_recall hit (id=1383 sim=0.70); skills count measured live: walker 89 active roots, snapshot 89, 459 SKILL.md on disk, 370 in support dirs
- [x] 1. skills-count "bug" RESOLVED — not a bug: walker prunes references/templates/assets/scripts by design; header 91 = boot count, 2 skills deleted this session
- [ ] 2. write SVG ~/.daedalus/architecture.svg — panels: tape budget, prompt builder, off-tape substrate, growth curve, re-entry arrows
- [ ] 3. verify: python xml parse + tag balance; then report

## Decisions
- standalone SVG file (not matplotlib) — user asked explicitly for SVG this time
- numbers only from this session's live measurements: 89 roots / 459 files / 370 support-dir / soak 1200-2400-3600 / pool 240 / RRF k=60 / ceiling 0.55 / floor 0.30 / Jaccard 0.55 / carry 10 turns

## Notes
- earlier claim "461 on disk, stale header" was WRONG (counted support-dir files); corrected above.
