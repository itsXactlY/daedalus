---
name: youtube-content
description: >
  Fetch YouTube video transcripts and transform them into structured content
  (chapters, summaries, threads, blog posts). Also supports FULL WATCH MODE:
  download video, extract scene storyboards, and analyze frames visually
  (with local ollama/moondream fallback when cloud vision is unavailable).
  Use when the user shares a YouTube URL or video link, asks to summarize a
  video, says "watch this video", requests a transcript, or wants to extract
  and reformat content from any YouTube video.
---

# YouTube Content Tool

Extract transcripts from YouTube videos and convert them into useful formats.

## Setup

```bash
pip install youtube-transcript-api
```

## Helper Script

`SKILL_DIR` is the directory containing this SKILL.md file. The script accepts any standard YouTube URL format, short links (youtu.be), shorts, embeds, live links, or a raw 11-character video ID.

```bash
# JSON output with metadata
python3 SKILL_DIR/scripts/fetch_transcript.py "https://youtube.com/watch?v=VIDEO_ID"

# Plain text (good for piping into further processing)
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only

# With timestamps
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --timestamps

# Specific language with fallback chain
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --language tr,en
```

## Output Formats

After fetching the transcript, format it based on what the user asks for:

- **Chapters**: Group by topic shifts, output timestamped chapter list
- **Summary**: Concise 5-10 sentence overview of the entire video
- **Chapter summaries**: Chapters with a short paragraph summary for each
- **Thread**: Twitter/X thread format — numbered posts, each under 280 chars
- **Blog post**: Full article with title, sections, and key takeaways
- **Quotes**: Notable quotes with timestamps

### Example — Chapters Output

```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
```

## Workflow

1. **Fetch** the transcript using the helper script with `--text-only --timestamps`.
2. **Validate**: confirm the output is non-empty and in the expected language. If empty, retry without `--language` to get any available transcript. If still empty, tell the user the video likely has transcripts disabled.
3. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
4. **Transform** into the requested output format. If the user did not specify a format, default to a summary.
5. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.

## Error Handling
## Error Handling
- **Transcript disabled**: tell the user; suggest they check if subtitles are available on the video page.
- **Private/unavailable video**: relay the error and ask the user to verify the URL.
- **No matching language**: retry without `--language` to fetch any available transcript, then note the actual language to the user.
- **Dependency missing**: run `pip install youtube-transcript-api` and retry.

## Full Watch Mode (transcript + visual channel)

When the user says "watch" (vs. summarize), they expect BOTH channels covered and an honest report on coverage quality. Full pipeline + pitfalls: see `references/watch-mode.md`.

Quick order of operations:
1. Metadata/chapters: `yt-dlp --dump-json URL` (title, duration, chapters, description).
2. Transcript: auto-subs via yt-dlp (`--write-auto-subs --skip-download --sub-langs en`) or the helper script — this is the 100%-coverage audio channel.
3. Video download (lowest sufficient res, e.g. `-f "best[height<=480]"`), then ffmpeg scene-detect storyboards at 2–3 granularities:
   `ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)',scale=320:180,tile=6x5" -frames:v 1 storyboard.mhtml -q:v 9`
   (MHTML tile output embeds each cell as JPEG; parse with `email` module.)
4. Vision fallback ladder — CHECK BEFORE SPENDING CALLS:
   a. openrouter vision_analyze → if 402/credit error, STOP retrying it.
   b. Check local ollama FIRST for vision models (`ollama list`): moondream/qwen-vl/llava may already be pulled.
   c. NVIDIA fallback script if present (e.g. ~/projects/comic/_build/vision_probe.py).
5. Frame analysis discipline (hard-won):
   - Use ollama REST API (:11434, base64 image in JSON) — CLI arg parsing mangles image paths.
   - Query frames INDIVIDUALLY. Contact sheets/grids are flaky: empty responses or hallucinated garbage (counting sequences). One frame per call, low temperature (0.1–0.2).
   - Soft upscaled cells (160x90→bigger) mostly return empty. Retry once; if still empty, abandon that cell — don't burn time.
   - Hi-res single images (thumbnails ≥1280px) work reliably.
6. Companion-article trick: creator videos usually have a companion blog post (check video description) carrying the same charts/stats at full resolution WITH named sources. Fetching it legitimately covers the data-visual channel when frames are unreadable.
7. Report honestly: which channels were fully covered (audio = verbatim transcript) vs degraded (visual = partial), and what method got you there.
