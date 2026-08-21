# Multi-Machine SSH Dispatch for Autonomous Loops

When the orchestrator (brain) and GPU worker live on different machines, the loop needs to shuttle commands and data across SSH without breaking on quoting, special characters, or missing tools.

## Architecture Pattern

```
cron on desk ──SSH──► tpad (brain) ──SSH──► desk (GPU worker)
                           │                      │
                           │ concept JSON          │ pipeline results
                           ▼                      ▼
                      mazemaker                 output/videos/
```

## Critical: Shell Quoting Through Multi-Hop SSH

**The problem:** Script text with spaces, quotes, newlines, or special characters gets mangled passing through `ssh host1 'ssh host2 "python3 script.py --arg \"$SCRIPT\""'`. Each level of nesting adds quoting complexity.

**The fix — base64 encoding:**

```bash
# On the ORIGINATING machine (concept generation):
SCRIPT_TEXT="The labyrinth of memory stretches before you..."
SCRIPT_B64=$(echo -n "$SCRIPT_TEXT" | base64 -w0)

# SSH to target, decode in the remote shell:
ssh target 'bash -c '\''
  SCRIPT_B64="'"$SCRIPT_B64"'"
  SCRIPT_TEXT=$(echo "$SCRIPT_B64" | base64 -d)
  python3 script.py --script "$SCRIPT_TEXT"
'\'' 2>&1'
```

**Alternative — file-based transcript (preferred for long text):**

```python
# Write script to temp file
with open('page_script.txt', 'w') as f:
    f.write(script_text)

# SSH copies the file, then the remote reads it
# Or: scp the file, then ssh runs the command referencing the filepath

# Inside generate_voiceover.py, read from file path:
if script_path and os.path.exists(script_path):
    with open(script_path, 'r') as f:
        text = f.read()
```

**Always prefer the file-based approach** when text exceeds ~200 chars. It eliminates all quoting issues and works across any number of SSH hops.

## Worker Script Exit Code Pitfall

When using `ssh worker 'cd /dir && python3 script.py'`, the exit code reflects the LAST command in the chain. If `cd` succeeds but `python3` fails, the SSH exit code is the python3 exit code (good). But if `cd` fails (directory doesn't exist), the pipe chain stops and SSH returns 127 or 1 with no diagnostic.

**Fix:** Use `&&` or `set -euo pipefail` to chain, and always check exit code:

```bash
if ! ssh desk "cd ~/mazemaker-maze && python3 scripts/pipeline_worker.py '$RUN_ID' --script '$SCRIPT'"; then
    log "SSH command failed"
fi
```

## Base64 Encoding with Python (For Subprocess Calls)

When passing script text to a subprocess.Popen() call (not shell), write to a temp file instead:

```python
# BAD: passing text as command-line argument
subprocess.run([sys.executable, 'script.py', text], ...)
# → breaks on newlines, quotes, unicode

# GOOD: write to file, pass filepath
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
    f.write(text)
    script_path = f.name
subprocess.run([sys.executable, 'script.py', script_path], ...)
os.unlink(script_path)
```

## Tool Availability Check Across Machines

Before dispatching work to a remote machine, verify the remote has the required tools:

```bash
ssh worker 'which python3 && python3 -c "import torch; print(torch.cuda.is_available())" && which ffmpeg'
```

If any check fails, the orchestrator should fall back gracefully (e.g., generate a text-only output or skip the GPU-dependent phase).

## Stderr/Stdout Confusion

Some warnings go to stdout instead of stderr (e.g., HuggingFace flash-attn warnings, PyTorch import-side prints). When using `capture_output=True`, always parse stdout defensively:

```python
# Scan backwards for last valid JSON
for line in reversed(result.stdout.strip().split('\n')):
    line = line.strip()
    if line.startswith('{') and line.endswith('}'):
        data = json.loads(line)
        break
```
