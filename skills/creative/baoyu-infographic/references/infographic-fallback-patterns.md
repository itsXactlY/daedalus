# Infographic Fallback Patterns

## HTML + Playwright Fallback

Use when `image_generate` fails due to missing `FAL_KEY` or unavailable credits.

**Verified recipe from session:**

```bash
# 1. Create HTML with inline CSS
# 2. Render to PNG
npx playwright screenshot --viewport-size=1920,1080 infographic.html infographic.png

# 3. Verify
file infographic.png  # Should show PNG, dimensions match viewport
ls -lh infographic.png # Should be >100KB
```

**Known issues from session:**
- Radial/hub-spoke layouts cause text overlap and label mangling
- Center text may render incorrectly (e.g., "1M" → "11M")
- Labels get mangled ("MCP" → "MCI", "MEM-03" → "MEI-03")
- Text is cramped at 1920×1080 for 8+ sections

**Fixes:**
- Use `bento-grid` or `linear-progression` instead of radial for text-heavy infographics
- Increase canvas to 2560×1440 or 3200×1800
- Use absolute positioning with explicit coordinates
- Add more padding between sections

## User Quality Correction Pattern

When the user says:
- "it's all trash"
- "pathetic" (via GIF or text)
- "this sucks"
- "why is it like this"

**Do NOT** keep iterating on the same approach. The user is telling you the method is wrong.

**Action:**
1. Acknowledge the issue directly
2. Switch methods (HTML → ComfyUI, or vice versa)
3. Ask for a specific reference image if the style is unclear
4. Use subagents to generate multiple variants in parallel if the user wants options

## ComfyUI for Infographics

When the user says "use the comfy setup" or provides a reference image URL, use ComfyUI with SDXL:

```bash
# Start server if not running
cd /home/alca/comfy/ComfyUI && .venv/bin/python main.py --listen 127.0.0.1 --port 8188

# Check models
cd /home/alca/comfy/ComfyUI && comfy model list

# Download SDXL if needed (public, no auth)
curl -L -o /home/alca/comfy/ComfyUI/models/checkpoints/sd_xl_base_1.0.safetensors \
  https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

# Run workflow
python3 ~/.hermes/skills/creative/comfyui/scripts/run_workflow.py \
  --workflow /home/alca/comfy/ComfyUI/workflows/<topic>-infographic-sdxl.json \
  --args '{"seed": 42, "steps": 30}' \
  --output-dir /home/alca/comfy/ComfyUI/output/<topic>
```

See `comfyui/references/infographic-generation-recipe.md` for the full workflow template.
