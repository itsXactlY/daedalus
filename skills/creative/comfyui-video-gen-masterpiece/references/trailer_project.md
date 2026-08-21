# Trailer Project Details

- **Project directory**: `/home/alca/projects/video/lab/trailer/`
- **Audio track**: `trailer-soundtrack.flac` – use as the audio conditioning source for LTX‑2 audio‑sync workflow.
- **HTML script**: `trailer-viral.html` – contains the textual description of the desired shots. Extract the prompt (or ask the user) and feed it to the CLIP Text Encode nodes.

### Suggested final‑touch workflow
1. Load the audio file via the `LTXVAudioVAELoader` (or `AudioFile` node) and set it as the audio conditioning input.
2. Parse the HTML for the shot list (or manually copy the prompt) and generate each shot using the appropriate model (WAN 2.2 for action, HunyuanVideo for establishing shots, LTX‑2 for dialogue).
3. Upscale to 1080p with the VideoHelperSuite upscaler if needed.
4. Export to MP4 (`h264-mp4` format) and place the final video in the project directory.

### Tips
- Keep resolution at 720p during iteration, upscale only for the final render to conserve VRAM.
- Use the `GGUF Q4` model for WAN 2.2 when on a 16 GB card.
- Ensure the audio file sample rate is 16 kHz for optimal sync with LTX‑2.
