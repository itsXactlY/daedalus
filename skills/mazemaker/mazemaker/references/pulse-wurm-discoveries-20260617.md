# Pulse-Wurm 2.0 Discoveries - 2026-06-17

## Session Summary
- **Tick**: 2026-06-17T15:33:56
- **Seeds processed**: 3
- **Novel discoveries**: 6
- **Consecutive empty streak**: Reset to 0

## Key Discoveries

### 1. skill-of-skills: The Autonomous Discovery Engine
- **URL**: https://github.com/the911fund/skill-of-skills
- **Seed**: Claude Code MCP integration
- **Summary**: Quality-ranked directory for AI coding skills with 875 skills across 10 types, ranked by structural quality, reputation, and proven adoption. Features Hermes Agent, Claude Code skills, and MCP server integrations prominently.
- **Key Finding**: This is a curated skill directory that could be integrated with the mazemaker discovery memory system.

### 2. NVIDIA/Model-Optimizer
- **URL**: https://github.com/NVIDIA/Model-Optimizer
- **Seed**: VLLM inference optimization
- **Summary**: Unified library of SOTA model optimization techniques (quantization, distillation, pruning, NAS, speculative decoding) for vLLM, TensorRT-LLM, and Transformers.
- **Key Finding**: Production-ready optimization stack for LLM inference with multi-framework support.

### 3. intel/auto-round
- **URL**: https://github.com/intel/auto-round
- **Seed**: VLLM inference optimization
- **Summary**: High-accuracy low-bit LLM inference optimization for CPU/XPU/CUDA with full compatibility with vLLM, SGLang, and Transformers.
- **Key Finding**: Intel's quantization solution achieving near-optimal INT4/INT8 LLM inference across multiple backends.

### 4. stacklok/toolhive
- **URL**: https://github.com/stacklok/toolhive
- **Seed**: MCP protocol security
- **Summary**: Enterprise-grade platform for running and managing Model Context Protocol (MCP) servers.
- **Key Finding**: Security-focused MCP server management platform with potential for enterprise deployments.

### 5. Tencent/AI-Infra-Guard
- **URL**: https://github.com/Tencent/AI-Infra-Guard
- **Seed**: AI agent security vulnerabilities
- **Summary**: Full-stack AI Red Teaming platform with OpenClaw Security Scan, Agent Scan, Skills Scan, MCP Scan, AI Infra scan, and LLM jailbreak evaluation.
- **Key Finding**: Comprehensive AI security platform with specific MCP scanning capabilities.

### 6. praetorian-inc/augustus
- **URL**: https://github.com/praetorian-inc/augustus
- **Seed**: LLM jailbreaking techniques
- **Summary**: LLM security testing framework for detecting prompt injection, jailbreaks, and adversarial attacks with 190+ probes across 28 providers.
- **Key Finding**: Enterprise-grade jailbreak detection framework with multi-provider support.

## Implementation Notes

### GitHub API Fallback Pattern
When MCP tools are unreachable:

```python
import requests

def github_search(query, per_page=5):
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "updated", "per_page": per_page}
    headers = {"Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    return resp.json().get("items", [])
```

### Rate Limit Handling
- Unauthenticated: 60 requests/hour
- Authenticated (GITHUB_TOKEN): 5000 requests/hour
- Add token via: `export GITHUB_TOKEN=*** Duplicate Detection
- Check `visited_urls` from state file
- Use topic similarity matching to avoid semantic duplicates
- Skip URLs already in visited set