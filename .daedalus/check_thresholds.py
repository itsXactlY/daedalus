"""Ad-hoc: what the real config thresholds become local vs remote."""
import sys
sys.path.insert(0, ".")
from unittest.mock import patch
from agent.context_compressor import ContextCompressor

PCT, CEIL, RATIO = 0.5, 32000, 0.1

for ctx in (262144, 200000, 1000000):
    kw = dict(model="m", threshold_percent=PCT, max_tokens=CEIL,
              summary_target_ratio=RATIO, quiet_mode=True, config_context_length=ctx)
    with patch("agent.context_compressor.get_model_context_length", return_value=ctx):
        loc = ContextCompressor(base_url="http://127.0.0.1:8080/v1", provider="local", **kw)
        rem = ContextCompressor(base_url="https://api.openai.com/v1", provider="openai", **kw)
    early = next((t for t in range(0, rem.threshold_tokens, 100) if rem._sparing_trigger(t) > 0), None)
    print(f"ctx={ctx:>8}  local_trigger={loc.threshold_tokens:>8}  remote_trigger={rem.threshold_tokens:>8}"
          f"  summary_cap={rem.max_summary_tokens:>6}  tail={rem.tail_token_budget:>6}"
          f"  remote_early_from={early}")
