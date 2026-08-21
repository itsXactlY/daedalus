# Containerfile GPU — pip → uv Migration (2026-05-29)

## Why

`pip install --no-cache-dir` on `--no-cache` builds keeps timing out on
PyPI (`ReadTimeoutError: HTTPSConnectionPool`). `uv` is ~10-100x faster
and avoids the timeout issue by using parallel downloads + aggressive
caching.

## Changes applied to `Containerfile.gpu.nuitka`

Three hunks in the builder (Stage 1) and one in the runtime (Stage 2):

### Builder Stage — Nuitka + setuptools install (stage 1)

```dockerfile
# BEFORE:
RUN pip install --no-cache-dir nuitka==2.5.4 setuptools wheel ordered-set

# AFTER:
RUN pip install uv && uv pip install --system --no-cache nuitka==2.5.4 setuptools wheel ordered-set
```

### Builder Stage — requirements install (stage 1)

```dockerfile
# BEFORE:
RUN pip install --no-cache-dir -r /build/requirements.gpu.txt

# AFTER:
RUN uv pip install --system --no-cache -r /build/requirements.gpu.txt
```

### Runtime Stage — uv bootstrap + requirements install (stage 2)

The runtime stage (FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime) does
NOT inherit uv from the builder stage. It must be installed fresh:

```dockerfile
# BEFORE:
RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 libpq5 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# AFTER:
RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 libpq5 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# And for the requirements:
# BEFORE:
RUN pip install --no-cache-dir -r requirements.gpu.txt && \
    rm /app/requirements.gpu.txt

# AFTER:
RUN uv pip install --system --no-cache -r /app/requirements.gpu.txt && \
    rm /app/requirements.gpu.txt
```

## Key differences pip vs uv in containers

| pip | uv equivalent | Why |
|-----|--------------|-----|
| `pip install` | `uv pip install --system` | uv refuses to run without active venv; `--system` = use system Python |
| `--no-cache-dir` | `--no-cache` | Different flag name |
| `-r requirements.txt` | `-r /absolute/path/requirements.txt` | uv resolves relative paths differently; use absolute paths in containers |

## Each stage needs uv installed separately

Container stages are independent layers. uv installed in Stage 1 is NOT
present in Stage 2. Both stages must `pip install uv` first.
