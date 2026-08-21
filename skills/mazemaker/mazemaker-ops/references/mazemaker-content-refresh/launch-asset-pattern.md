# Launch-Asset Library Anatomy (observed, condensed)

A mature Mazemaker launch-asset library (~16 files under `~/.mazemaker-notes/launch-assets/`):

- `00-README.md` — META + source-of-truth. Numbers cross-check table with the rule
  "if any number on the site / in any post / in the video disagrees, the table wins".
  Open-decisions log (resolved vs open). Launch-sequence drop plan (T-0..T+48h).
  Don't-touch list. This file anchors everything.
- Platform drafts (the postings themselves):
  - `01-hn-show-hn.md` — Hacker News Show HN, locked title (≤80 chars), body + first
    self-comment with weakness disclosure, risk-watch, voice rule.
  - `02-reddit-localllama.md` — warm/personal hook (the 270M-Pi moment is the lede).
  - `03-twitter-thread-launch.md` — 10-tweet thread, one image per tweet, engagement
    playbook, anti-rules.
  - `04-linkedin-launch.md` — operator voice, no emoji, hourly comment plan.
  - `05-press-kit.md` — 30s/60s pitch, key facts, pricing, differentiators, competitor
    table, common Q&A, embargo terms.
  - `06-twitter-day2-federation.md` — 7-tweet Day-2 beat (federation).
  - `07-twitter-day3-rebake.md` — 8-tweet Day-3 beat (self-improvement loop) + LinkedIn
    article cross-post.
  - `08-video-shotlist-v10.md` — 90s trailer shotlist, VO lines, source-clip checklist,
    edit-pass checklist, distribution, risk mitigation.
  - `09-reddit-machinelearning.md` — academic `[R]` framing, no pricing, no homepage link.
  - `10-hn-backup-post.md` — emergency HN repost with different angle if primary is
    flag-banned.
- `11-press-assets-layout.md` — `assets.mazemaker.online/press/` directory tree + rendered
  `index.html` + operator action checklist.
- `12-journalist-embargo-dms.md` — 8 individually-written DMs, each matched to published
  interests, plus reach-out execution rules.

GAPS that are NAMED in the README drop-sequence but had NO draft file until added:
- `13-blog-post-launch.md` — the long-form blog anchor (T-0 15:00:00, unlisted→public).
- `14-social-vertical-captions.md` — IG Reels / TikTok / YT Shorts 9:16 captions.
- `15-personal-network-blurb.md` — Discord / Telegram / Signal operator-network announce.

Convention: every draft keeps a `Voice rule` / `Anti-rules` / `Engagement plan` block.
Preserve these — they are load-bearing, not boilerplate. Per-platform facts (benchmarks,
pricing, weaknesses) must match the README table exactly.
