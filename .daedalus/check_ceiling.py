"""Print the real compression triggers for local vs remote, with the live config.

Run: python .daedalus/check_ceiling.py
"""
import sys

sys.path.insert(0, ".")
from agent.context_compressor import ContextCompressor  # noqa: E402

CASES = [
    # label,                  model,                 provider,      base_url,                        ctx
    ("daedalus doctor (local)", "qwen3-27b",         "daedalus",  "http://127.0.0.1:8080/v1",    262144),
    ("daedalus over LAN",       "qwen3-27b",         "daedalus",  "http://192.168.1.5:8080/v1",  262144),
    ("deepseek",                "deepseek-chat",     "deepseek",  "https://api.deepseek.com/v1",   163840),
    ("openrouter",              "anthropic/claude",  "openrouter", "https://openrouter.ai/api/v1", 200000),
    ("big-window provider",     "some-1m",           "someprov",  "https://api.example.com/v1",  1000000),
]

print(f"{'case':24} {'window':>9} {'local-line':>11} {'real-line':>10} {'spares-from':>12}  verdict")
for label, model, provider, base_url, ctx in CASES:
    cc = ContextCompressor(
        model=model,
        threshold_percent=0.50,      # compression.threshold
        protect_first_n=4,
        protect_last_n=6,
        summary_target_ratio=0.10,   # compression.target_ratio
        quiet_mode=True,
        base_url=base_url,
        provider=provider,
        max_tokens=32000,            # compression.max_tokens
        config_context_length=ctx,
    )
    local_line = cc._local_ceiling_trigger()
    real_line = cc.threshold_tokens
    first = None
    probe = 1000
    while probe <= ctx:
        if cc._sparing_trigger(probe):
            first = probe
            break
        probe += 1000
    ceiling = "on " if cc._ceiling_applies() else "off"
    spared = f"{first:,}" if first else "never"
    if first and first < real_line:
        verdict = f"EARLY at {first:,} (below real line {real_line:,})"
    else:
        verdict = f"waits for real line {real_line:,}"
    print(f"{label:24} {ctx:>9,} {local_line:>11,} {real_line:>10,} {spared:>12}  ceiling {ceiling} -> {verdict}")
