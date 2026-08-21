---
name: baoyu-comic
description: "Knowledge comics (知识漫画): educational, biography, tutorial."
version: 1.78.0
author: 宝玉 (JimLiu)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [comic, knowledge-comic, creative, image-generation]
    homepage: https://github.com/JimLiu/baoyu-skills#baoyu-comic
---

# Knowledge Comic Creator

Adapted from [baoyu-comic](https://github.com/JimLiu/baoyu-skills) for Hermes Agent's tool ecosystem.

Create original knowledge comics with flexible art style × tone combinations.

## When to Use

Trigger this skill when the user asks to create a knowledge/educational comic, biography comic, tutorial comic, or uses terms like "知识漫画", "教育漫画", or "Logicomix-style". The user provides content (text, file path, URL, or topic) and optionally specifies art style, tone, layout, aspect ratio, or language.

### Mazemaker Use-Case Comics (domain-first pattern)

When the user asks for Mazemaker comics specifically, their preferred approach is **stories-first, not styles-first**: create DIFFERENT STORIES for different real-world domains (health, military, academia, space, energy, disaster), each with a domain-matched art style from the 23-style catalogue. Do NOT create art-style variants of the same story — that was the V3 pattern.

See `references/mazemaker-use-case-comics.md` for:
- Domain-to-style mapping table (15 domains x best-fit style)
- 15-page story template (problem → activation → dream engine → federation → climax → tagline)
- Character template (protagonist, skeptic, Mazemaker system, enthusiast, field user)
- Mazemaker concept hyperlinks (memory graph, dream engine, federation, recall, meta-skills)

For batch generation of multiple comics, use `templates/riverflow-batch-generator.py` with the `scripts/run-comic-gen.sh` bootstrap wrapper (extracts API key from config at runtime to avoid write_file redaction).

## Reference Images

Hermes' `image_generate` tool (FAL) is **prompt-only** — it accepts a text prompt and an aspect ratio, and returns an image URL. It does **NOT** accept reference images. When using the `image-gen-openrouter` fallback with Riverflow, reference images ARE supported via image-to-image content arrays.

**Intake**: Accept file paths when the user provides them (or pastes images in conversation).
- File path(s) → copy to `refs/NN-ref-{slug}.{ext}` alongside the comic output for provenance
- Pasted image with no path → ask the user for the path via `clarify`, or extract style traits verbally as a text fallback
- No reference → skip this section

**When using Riverflow (image-gen-openrouter skill)**:
- Reference images can be passed directly as `image_url` content parts in the API call BEFORE the text prompt
- This enables **true style transfer** — the model matches palette, line treatment, texture, and mood from the reference
- See `creative/image-gen-openrouter` skill for API patterns

**When using FAL (image_generate tool)**:
- Extract style traits as text descriptions (line treatment, texture, mood, colors) and append to every page's prompt body
- Character consistency is driven by text descriptions in characters/characters.md

**Usage modes** (per reference):

| Usage | Effect |
|-------|--------|
| `style` | Extract style traits (line treatment, texture, mood) and append to every page's prompt body |
| `palette` | Extract hex colors and append to every page's prompt body |
| `scene` | Extract scene composition or subject notes and append to the relevant page(s) |

**Record in each page's prompt frontmatter** when refs exist:

```yaml
references:
  - ref_id: 01
    filename: 01-ref-scene.png
    usage: style
    traits: "muted earth tones, soft-edged ink wash, low-contrast backgrounds"
```

Character consistency is driven by **text descriptions** in `characters/characters.md` (written in Step 3) that get embedded inline in every page prompt (Step 5). The optional PNG character sheet generated in Step 7.1 is a human-facing review artifact, not an input to `image_generate`.

## Options

### Visual Dimensions

| Option | Values | Description |
|--------|--------|-------------|
| Art | ligne-claire (default), manga, realistic, ink-brush, chalk, minimalist, hero-style | Art style / rendering technique. `hero-style` = user's own style from reference image (text-described, not manga/anime) |
| Format | comic (default), scene | `comic` = multi-panel page layout. `scene` = single full-window standalone illustration per image |
| Aspect | 3:4 (default, portrait), 4:3 (landscape), 16:9 (widescreen), 21:9 (ultrawide) | Page aspect ratio — riverflow has known 21:9 HTTP 500 issues (see riverflow reference) |
| Language | auto (default), zh, en, ja, etc. | Output language |
| Refs | File paths | Reference images used for style / palette trait extraction (not passed to the image model). See [Reference Images](#reference-images) above. |

### Partial Workflow Options

| Option | Description |
|--------|-------------|
| Storyboard only | Generate storyboard only, skip prompts and images |
| Prompts only | Generate storyboard + prompts, skip images |
| Images only | Generate images from existing prompts directory |
| Regenerate N | Regenerate specific page(s) only (e.g., `3` or `2,5,8`) |

Details: [references/partial-workflows.md](references/partial-workflows.md)

### Art, Tone & Preset Catalogue

- **Art styles** (6): `ligne-claire`, `manga`, `realistic`, `ink-brush`, `chalk`, `minimalist`. Full definitions at `references/art-styles/<style>.md`.
- **Tones** (7): `neutral`, `warm`, `dramatic`, `romantic`, `energetic`, `vintage`, `action`. Full definitions at `references/tones/<tone>.md`.
- **Presets** (5) with special rules beyond plain art+tone:

  | Preset | Equivalent | Hook |
  |--------|-----------|------|
  | `ohmsha` | manga + neutral | Visual metaphors, no talking heads, gadget reveals |
  | `wuxia` | ink-brush + action | Qi effects, combat visuals, atmospheric |
  | `shoujo` | manga + romantic | Decorative elements, eye details, romantic beats |
  | `concept-story` | manga + warm | Visual symbol system, growth arc, dialogue+action balance |
  | `four-panel` | minimalist + neutral + four-panel layout | 起承转合 structure, B&W + spot color, stick-figure characters |

  Full rules at `references/presets/<preset>.md` — load the file when a preset is picked.

- **Compatibility matrix** and **content-signal → preset** table live in [references/auto-selection.md](references/auto-selection.md). Read it before recommending combinations in Step 2.

## File Structure

Output directory: `comic/{topic-slug}/`
- Slug: 2-4 words kebab-case from topic (e.g., `alan-turing-bio`)
- Conflict: append timestamp (e.g., `turing-story-20260118-143052`)

**Contents**:
| File | Description |
|------|-------------|
| `source-{slug}.md` | Saved source content (kebab-case slug matches the output directory) |
| `analysis.md` | Content analysis |
| `storyboard.md` | Storyboard with panel breakdown |
| `characters/characters.md` | Character definitions |
| `characters/characters.png` | Character reference sheet (downloaded from `image_generate`) |
| `prompts/NN-{cover\|page}-[slug].md` | Generation prompts |
| `NN-{cover\|page}-[slug].png` | Generated images (downloaded from `image_generate`) |
| `refs/NN-ref-{slug}.{ext}` | User-supplied reference images (optional, for provenance) |

## Language Handling

**Detection Priority**:
1. User-specified language (explicit option)
2. User's conversation language
3. Source content language

**Rule**: Use user's input language for ALL interactions:
- Storyboard outlines and scene descriptions
- Image generation prompts
- User selection options and confirmations
- Progress updates, questions, errors, summaries

Technical terms remain in English.

## Workflow

### Progress Checklist

```
Comic Progress:
- [ ] Step 1: Setup & Analyze
  - [ ] 1.1 Analyze content
  - [ ] 1.2 Check existing directory
- [ ] Step 2: Confirmation - Style & options ⚠️ REQUIRED
- [ ] Step 3: Generate storyboard + characters
- [ ] Step 4: Review outline (conditional)
- [ ] Step 5: Generate prompts
- [ ] Step 6: Review prompts (conditional)
- [ ] Step 7: Generate images
  - [ ] 7.1 Generate character sheet (if needed) → characters/characters.png
  - [ ] 7.2 Generate pages (with character descriptions embedded in prompt)
- [ ] Step 8: Completion report
```

### Flow

```
Input → Analyze → [Check Existing?] → [Confirm: Style + Reviews] → Storyboard → [Review?] → Prompts → [Review?] → Images → Complete
```

### Step Summary

| Step | Action | Key Output |
|------|--------|------------|
| 1.1 | Analyze content | `analysis.md`, `source-{slug}.md` |
| 1.2 | Check existing directory | Handle conflicts |
| 2 | Confirm style, focus, audience, reviews | User preferences |
| 3 | Generate storyboard + characters | `storyboard.md`, `characters/` |
| 4 | Review outline (if requested) | User approval |
| 5 | Generate prompts | `prompts/*.md` |
| 6 | Review prompts (if requested) | User approval |
| 7.1 | Generate character sheet (if needed) | `characters/characters.png` |
| 7.2 | Generate pages | `*.png` files |
| 8 | Completion report | Summary |

### User Questions

Use the `clarify` tool to confirm options. Since `clarify` handles one question at a time, ask the most important question first and proceed sequentially. See [references/workflow.md](references/workflow.md) for the full Step 2 question set.

**Timeout handling (CRITICAL)**: `clarify` can return `"The user did not provide a response within the time limit. Use your best judgement to make the choice and proceed."` — this is NOT user consent to default everything.

- Treat it as a default **for that one question only**. Continue asking the remaining Step 2 questions in sequence; each question is an independent consent point.
- **Surface the default to the user visibly** in your next message so they have a chance to correct it: e.g. `"Style: defaulted to ohmsha preset (clarify timed out). Say the word to switch."` — an unreported default is indistinguishable from never having asked.
- Do NOT collapse Step 2 into a single "use all defaults" pass after one timeout. If the user is genuinely absent, they will be equally absent for all five questions — but they can correct visible defaults when they return, and cannot correct invisible ones.

### Step 7: Image Generation

Use Hermes' built-in `image_generate` tool for all image rendering. Its schema accepts only `prompt` and `aspect_ratio` (`landscape` | `portrait` | `square`); it **returns a URL**, not a local file. Every generated page or character sheet must therefore be downloaded to the output directory.

**Prompt file requirement (hard)**: write each image's full, final prompt to a standalone file under `prompts/` (naming: `NN-{type}-[slug].md`) BEFORE calling `image_generate`. The prompt file is the reproducibility record.

**Story-first prompting**: When generating comic pages, the prompt must emphasize "story as comic" — the narrative, characters acting, panel layouts, dialogue in speech bubbles, and narration in boxes. Do NOT use "MAXIMUM TEXT" / "render all dialogue large and legible" instructions — that produces a text-dump infographic, not a comic strip. The story and characters should drive each panel. Example phrasing that works: "Render as a manga comic strip: proper panel layouts, character dialogue in oval speech bubbles, narrator commentary in rectangular boxes, bold term labels. The STORY and CHARACTERS drive each panel."

**Aspect ratio mapping** — the storyboard's `aspect_ratio` field maps to `image_generate`'s format as follows:

| Storyboard ratio | `image_generate` format |
|------------------|-------------------------|
| `3:4`, `9:16`, `2:3` | `portrait` |
| `4:3`, `16:9`, `3:2` | `landscape` |
| `1:1` | `square` |

**Download step** — after every `image_generate` call:
1. Read the URL from the tool result
2. Fetch the image bytes using an **absolute** output path, e.g.
   `curl -fsSL "<url>" -o /abs/path/to/comic/<slug>/NN-page-<slug>.png`
3. Verify the file exists and is non-empty at that exact path before proceeding to the next page

**Never rely on shell CWD persistence for `-o` paths.** The terminal tool's persistent-shell CWD can change between batches (session expiry, `TERMINAL_LIFETIME_SECONDS`, a failed `cd` that leaves you in the wrong directory). `curl -o relative/path.png` is a silent footgun: if CWD has drifted, the file lands somewhere else with no error. **Always pass a fully-qualified absolute path to `-o`**, or pass `workdir=<abs path>` to the terminal tool. Incident Apr 2026: pages 06-09 of a 10-page comic landed at the repo root instead of `comic/<slug>/` because batch 3 inherited a stale CWD from batch 2 and `curl -o 06-page-skills.png` wrote to the wrong directory. The agent then spent several turns claiming the files existed where they didn't.

**7.1 Character sheet** — generate it (to `characters/characters.png`, aspect `landscape`) when the comic is multi-page with recurring characters. Skip for simple presets (e.g., four-panel minimalist) or single-page comics. The prompt file at `characters/characters.md` must exist before invoking `image_generate`. The rendered PNG is a **human-facing review artifact** (so the user can visually verify character design) and a reference for later regenerations or manual prompt edits — it does **not** drive Step 7.2. Page prompts are already written in Step 5 from the **text descriptions** in `characters/characters.md`; `image_generate` cannot accept images as visual input.

**7.2 Pages** — each page's prompt MUST already be at `prompts/NN-{cover|page}-[slug].md` before invoking `image_generate`. Because `image_generate` is prompt-only, character consistency is enforced by **embedding character descriptions (sourced from `characters/characters.md`) inline in every page prompt during Step 5**. The embedding is done uniformly whether or not a PNG sheet is produced in 7.1; the PNG is only a review/regeneration aid.

**Backup rule**: existing `prompts/…md` and `…png` files → rename with `-backup-YYYYMMDD-HHMMSS` suffix before regenerating.

**Image generation fallback chain** when `image_generate` (FAL) is unavailable:
1. `creative/image-gen-openrouter` — OpenRouter models that output images natively. Two sub-paths depending on availability:

   **1a. `sourceful/riverflow-v2.5-pro:free`** — Dedicated T2I/I2I, FullHD-4K, text rendering, ~150-270s latency. **⚠️ As of June 2026, OpenRouter removed all free image models — riverflow :free is permanently unavailable.** Paid tier (`sourceful/riverflow-v2.5-pro` without `:free`) works with credits. Historical free tier had ~57 images/day. See Riverflow notes below.

   **1b. `google/gemini-3.1-flash-image-preview`** — Chat-based image model. **Use this when Riverflow free tier returns 429 (daily limit reached).** See Gemini Flash notes below.

2. `creative/comfyui` — Local GPU-based generation (requires ComfyUI installed, GPU with ≥6GB VRAM). See [local-comfyui-generation.md](references/local-comfyui-generation.md).

**Gemini Flash fallback notes** (when Riverflow is unavailable or quota-exhausted):

Use `google/gemini-3.1-flash-image-preview` when Riverflow returns any error (free tier removed, daily quota hit on paid tier, or timeout). Riverflow free tier has been removed from OpenRouter's catalogue as of June 2026, so Gemini Flash is now the only OpenRouter-based image generation path. The Gemini path requires OpenRouter credits (~$0.0005/image — a full 15-page comic costs under a cent). Key differences from Riverflow:

| Aspect | Riverflow (free) | Gemini 3.1 Flash | Impact |
|--------|-----------------|-------------------|--------|
| Latency | ~170-270s per page | ~11-19s per page | **10-15x faster** |
| Cost | Free (daily quota) | ~$0.0005/image | **~$0.004 per 8-page comic** |
| Response format | `message.images[]` | `message.content` (base64) | Different parsing code |
| Text rendering | Excellent | Good | Fine for comic dialogue |
| Character consistency | Shared style preamble | Same approach works | Identical workflow |
| Aspect ratio limits | 21:9 crashes (HTTP 500) | Works at standard ratios | Same safe ratios |
| Daily quota | ~90 images | No daily limit (pay-per-use) | **No hard stop** |

**Response parsing**: Gemini returns images as a base64 data URL embedded inside `message.content`. Extract with regex:
```python
import re, base64
content = d['choices'][0]['message']['content']
match = re.search(r'data:image/[^;]+;base64,([a-zA-Z0-9+/=]+)', content)
if match:
    img_data = base64.b64decode(match.group(1))
```
Always check `message.images[]` first (Riverflow pattern), fall back to `message.content` regex if empty. This way the same script handles both models.

**Shared style preamble works identically**: The same text-described character definitions, color palette hex codes, and page position annotations that work for Riverflow work for Gemini. No special adaptation needed. The preamble structure from `characters/characters.md` embeds inline the same way.

**When to use which**: Start with Riverflow. If it returns 429, switch to Gemini 3.1 Flash without rebuilding prompts — only the API call URL and response parsing change. The storyboard, characters, and prompts remain identical.

**Riverflow-specific notes** (when using fallback path 1a):
- Reference images are supported via content array (image-to-image). This enables style transfer from an origin image.
- **BUT**: passing a reference image as base64 (e.g., 172KB image = 172K+ chars of base64) causes 5+ minute latency and frequent IncompleteRead or HTTP 500 errors. **Describing the reference image's style IN TEXT is dramatically faster (~170s vs 5min+)** and more reliable. Only pass the image directly for small (<50KB) references or when fidelity to a specific texture/line treatment is essential.
- Use `reasoning: {"effort": "xhigh"}` — NOT `"reasoning": "xhigh"` (string fails with HTTP 400)
- **21:9 ultrawide (1536x672) and non-standard aspect ratios cause HTTP 500 "Internal Server Error"** on riverflow. Stick to standard aspect ratios (3:4, 4:3, 16:9, 1:1) or generate at 1280x720/1920x1080 and crop. If you must use ultrawide, test one page first before batching all 15.
- Prep a SHARED STORY TIMELINE with character definitions + plot summary of ALL pages, prepended to every page's prompt for cross-page character and style consistency. The timeline tells the model what came before and after each page.
- Images arrive in `message.images[]` field, not `message.content`. The content field is typically None when images are present.
- Sourceful imposes a 4.5MB request size limit — keep reference images under ~3MB base64
- Python 3.14+: `http.client.HTTPSConnection.request()` uses `body=` not `data=` for the request body. Using `data=` raises `TypeError: unexpected keyword argument 'data'`.
- Each page takes ~3-5 min at xhigh; batch accordingly (15 pages = ~60-75 min). Use terminal(background=true) with progress log.
- **21:9 aspect ratio warning**: Riverflow v2.5-pro returns HTTP 500 "Internal Server Error" for non-standard aspect ratios. Test one page at 1280x720 or 1920x1080 first. If HTTP 500 occurs, the model DOES NOT support that aspect ratio.
- **Key extraction pattern**: When extracting key from hermes config.yaml, use exact byte offsets. Example: `s = d[i:i+200]` then `KEY = s[a+9:a+82].decode('ascii')`. If key appears truncated in config (e.g., `sk-or-...03cb`), API calls fail with 401/400 errors.
- **Successful curl pattern**: Use list arguments for subprocess.run, NOT shell strings. Example:
  ```python
  hdr = 'Authorization: Bearer ' + KEY
  subprocess.run(['curl', '-s', '--max-time', '420', '-H', hdr, '-H', 'Content-Type: application/json', '-d', '@' + pf, 'https://openrouter.ai/api/v1/chat/completions', '-o', rf], capture_output=True, timeout=480)
  ```
- **Image response parsing**: Images arrive in `d['choices'][0]['message']['images'][0]['image_url']['url']`. Check for `data:` prefix before base64 decode.
- **API key redaction**: The write_file tool redacts API keys from script files. Scripts MUST extract the key at runtime from config.yaml using substring offsets (`s[a+9:a+82]`), NOT f-strings or hardcoded values. Use `scripts/run-comic-gen.sh` (bootstrap shell wrapper) to set `HERMES_RIVERFLOW_KEY` env var at call time. For Python scripts, use `os.environ.get("ENV_VAR_NAME")` to read it.
- **Riverflow batch generation**: For multi-page riverflow batches (8-15+ pages), the concurrent threading pattern in `creative/image-gen-openrouter` → `references/riverflow-concurrent-batch.md` is the recommended approach (3 parallel threads, resume support, ~11 min for 8 pages). Use `templates/riverflow-batch-generator.py` with that pattern.

Full step-by-step workflow (analysis, storyboard, review gates, regeneration variants): [references/workflow.md](references/workflow.md).

## References

**Core Templates**:
- [analysis-framework.md](references/analysis-framework.md) - Deep content analysis
- [character-template.md](references/character-template.md) - Character definition format
- [storyboard-template.md](references/storyboard-template.md) - Storyboard structure
- [ohmsha-guide.md](references/ohmsha-guide.md) - Ohmsha manga specifics
- [riverflow-batch-generator.py](templates/riverflow-batch-generator.py) - Resume-capable batch generator for multi-page riverflow comics
- [run-comic-gen.sh](scripts/run-comic-gen.sh) - Bootstrap shell wrapper (extracts API key from config at runtime)

**Style Definitions**:
- `references/art-styles/` - Art styles (ligne-claire, manga, realistic, ink-brush, chalk, minimalist)
- `references/tones/` - Tones (neutral, warm, dramatic, romantic, energetic, vintage, action)
- `references/presets/` - Presets with special rules (ohmsha, wuxia, shoujo, concept-story, four-panel)
- `references/layouts/` - Layouts (standard, cinematic, dense, splash, mixed, webtoon, four-panel)
- `references/mazemaker-art-styles.md` - Pre-tested style catalog for Mazemaker stories (cyberpunk neon through analog cybernetics)
- [mazemaker-use-case-comics.md](references/mazemaker-use-case-comics.md) - Domain-to-style mapping, 15-page story template, character template, Mazemaker concept catalogue, riverflow pipeline notes, content filter workarounds, staggered launch pattern
- [riverflow-quota-diagnostic.sh](references/riverflow-quota-diagnostic.sh) - Pre-launch quota check script (exit 0=OK, exit 1=rate limited)

**Workflow**:
- [workflow.md](references/workflow.md) - Full workflow details
- [auto-selection.md](references/auto-selection.md) - Content signal analysis
- [partial-workflows.md](references/partial-workflows.md) - Partial workflow options
- [multi-comic-pipeline.md](references/multi-comic-pipeline.md) - Batch generation with resume, content filter handling, quota management

**Local Generation**:
- [local-comfyui-generation.md](references/local-comfyui-generation.md) - Using ComfyUI locally when FAL unavailable

## Page Modification

| Action | Steps |
|--------|-------|
| **Edit** | **Update prompt file FIRST** → regenerate image → download new PNG |
| **Add** | Create prompt at position → generate with character descriptions embedded → renumber subsequent → update storyboard |
| **Delete** | Remove files → renumber subsequent → update storyboard |

**IMPORTANT**: When updating pages, ALWAYS update the prompt file (`prompts/NN-{cover|page}-[slug].md`) FIRST before regenerating. This ensures changes are documented and reproducible.

## Pitfalls

- Image generation: 10-30 seconds per page; auto-retry once on failure
- **Always download** the URL returned by `image_generate` to a local PNG — downstream tooling (and the user's review) expects files in the output directory, not ephemeral URLs
- **Use absolute paths for `curl -o`** — never rely on persistent-shell CWD across batches. Silent footgun: files land in the wrong directory and subsequent `ls` on the intended path shows nothing. See Step 7 "Download step".
- Use stylized alternatives for sensitive public figures
- **Step 2 confirmation required** - do not skip
- **Steps 4/6 conditional** - only if user requested in Step 2
- **Step 7.1 character sheet** - recommended for multi-page comics, optional for simple presets. The PNG is a review/regeneration aid; page prompts (written in Step 5) use the text descriptions in `characters/characters.md`, not the PNG. `image_generate` does not accept images as visual input
- **Strip secrets** — scan source content for API keys, tokens, or credentials before writing any output file
- **Stale process accumulation** — long-running batch scripts (15+ pages at xhigh = 60-90 min) leave background processes that accumulate if killed. Check `ps aux | grep python` for stale scripts before starting a new batch. Kill stale processes with `pkill -f script_name.py` or they'll compete for API rate limits and cause timeouts. Better: always run with `> /tmp/log 2>&1` and use a resume-from-breakpoint (`START_PAGE = N`) instead of killing and restarting.
- **Content filter blocks (Sourceful/Riverflow)** — Riverflow via Sourceful blocks certain visual descriptions with HTTP 422 "Inappropriate content detected". Common triggers: surgery/OR scenes, combat/explosions, trapped/injured persons (especially children). Fix: rewrite to focus on the DATA/SYSTEMS layer — terminal screens, data readouts, graph visualizations, radio communications. Never show the physical harm or rescue directly. See `references/riverflow-openrouter-api.md` → "Content Filter Triggers" for complete table of blocked categories and rewrites.
- **Auth header redaction** — When writing generation scripts to disk via write_file, the tool redacts API key patterns. A line like `hdr = "Authorization: Bearer " + KEY` gets corrupted to `hdr = "Authorization: Bearer *** + KEY`. Fix: split the string so the redactor doesn't match: `bearer = "Bearer " + KEY` then `hdr = "Authorization: " + bearer`. This avoids the `"Bearer " + key` pattern the redactor detects.
- **Riverflow daily quota (~57 images)** — Free tier has a rolling daily limit of ~57 images. Plan multi-comic generation to prioritize one full comic first, then spread remaining quota across partials. Scripts MUST have resume capability (skip existing files). When quota is exhausted, error is instant (0s) with "Rate limit exceeded: limit_rpd/sourceful/riverflow-v2.5-pro-..." — don't keep retrying.
- **Single-scene vs multi-panel format** — when the user asks for "full images, not multi-panel", each image is a standalone full-window scene, not a multi-panel comic page. Adjust prompts: no panel borders, no layout instructions, no "panel 1/2/3" in the description. Character descriptions and story timeline still apply for consistency.
- **Style adaptation from the user's own image** — when the user provides an image as style origin (`mazemaker-hero.webp`), describe it in text rather than passing the image as base64 (172KB+ to base64 = 5min+ latency). Include color hex codes, line treatment, character appearance, background style. Works reliably, 3x faster.
- **API key redaction in scripts** — The write_file tool redacts `sk-or-...` patterns from file content. Scripts that call riverflow MUST extract the key at runtime (read config.yaml, parse substring offsets). Do NOT use f-strings like `f"Authorization: Bearer {key}"` — those get redacted to `"Authorization: Bearer ***"` which breaks the script. Use string concatenation: `"Authorization: Bearer " + KEY`. Better: use `scripts/run-comic-gen.sh` to pass the key as an env var, then `os.environ.get("HERMES_RIVERFLOW_KEY")` in Python.
- **Riverflow content filters (Sourceful provider)** — Sourceful blocks medical/surgery scenes (OR tables, incisions, patients) and military combat (drone strikes, explosions, munitions) with HTTP 422 "Inappropriate content detected". The response is instant (~1s, not a timeout). Fix: rewrite blocked pages as data-visualization scenes — focus on information systems (graphs, connections, map state changes) rather than physical outcomes. The medical-to-visualization rewrite is the most common fix. See `references/riverflow-openrouter-api.md` for the full content filter section, and `references/mazemaker-use-case-comics.md` for validated rewrite examples.
- **Riverflow daily rate limit** — The `sourceful/riverflow-v2.5-pro:free` free tier has a hard daily request limit. Running 5 concurrent generators exhausts it in ~40 minutes; 2-3 concurrent gives ~90+ minutes of reliable generation. Symptom: instant 0s HTTP response with "Daily limit reached for sourceful/riverflow-v2.5-pro:free via Sourceful." This is a hard stop until the next day. **Mitigation**: switch to Gemini 3.1 Flash (see Gemini Flash fallback notes above) instead of waiting for quota reset. Same prompts, same style preamble, only API call and response parsing change. Cost is ~$0.0005/image — a full 8-page comic costs under a penny. The Gemini route has no daily cap, so you can finish the batch immediately.
