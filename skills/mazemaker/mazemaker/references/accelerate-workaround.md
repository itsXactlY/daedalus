# Loading Qwen2.5-Omni / HuggingFace Models Without accelerate

The `accelerate` package is NOT installed on this system (pip-install is blocked by PEP 668). 
However, recent transformers versions (5.x) have a check that calls 
`check_and_set_device_map` which raises `ValueError: requires accelerate`.

## The Fix: Monkey-patch

Patch the accelerate integration module BEFORE calling `from_pretrained()`:

```python
import transformers.integrations.accelerate as acc_mod

# Replace the check with a no-op
acc_mod.check_and_set_device_map = lambda dm: dm

# Now load without device_map
from transformers import (model_class)
model = model_class.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    device_map=None,       # Must be None — "auto" triggers accelerate
    trust_remote_code=True,
)
model = model.cuda().eval()  # Manually move to GPU afterwards
```

## Why This Works

`from_pretrained()` internally calls `check_and_set_device_map(device_map)` during its 
initialization sequence. By replacing it with an identity function, we skip the 
accelerate-dependency check entirely. The model loads weights-to-CPU by default, 
then we manually `.cuda()` after.

## When to Use

- Any HuggingFace model that calls `check_and_set_device_map`
- Transformers 4.45+ / 5.x
- Systems where pip install is blocked (PEP 668, system-managed Python)

## When NOT to Use

- If you need `device_map="auto"` for CPU offloading (this requires accelerate)
- If the model exceeds VRAM — monkey-patch disables the auto-offload feature

## Verification

```python
import torch
print(f"VRAM after load: {torch.cuda.memory_allocated()/1e9:.1f}GB")
print(f"Total VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB")
```
