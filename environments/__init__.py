"""
Daedalus-Agent Atropos Environments

Provides a layered integration between daedalus's tool-calling capabilities
and the Atropos RL training framework.

Core layers:
    - agent_loop: Reusable multi-turn agent loop with standard OpenAI-spec tool calling
    - tool_context: Per-rollout tool access handle for reward/verification functions
    - daedalus_base_env: Abstract base environment (BaseEnv subclass) for Atropos
    - tool_call_parsers: Client-side tool call parser registry for Phase 2 (VLLM /generate)

Concrete environments:
    - terminal_test_env/: Simple file-creation tasks for testing the stack
    - daedalus_swe_env/: SWE-bench style tasks with Modal sandboxes

Benchmarks (eval-only):
    - benchmarks/terminalbench_2/: Terminal-Bench 2.0 evaluation
"""

try:
    from environments.agent_loop import AgentResult, DaedalusAgentLoop
    from environments.tool_context import ToolContext
    from environments.daedalus_base_env import DaedalusAgentBaseEnv, DaedalusAgentEnvConfig
except ImportError:
    # atroposlib not installed — environments are unavailable but
    # submodules like tool_call_parsers can still be imported directly.
    pass

__all__ = [
    "AgentResult",
    "DaedalusAgentLoop",
    "ToolContext",
    "DaedalusAgentBaseEnv",
    "DaedalusAgentEnvConfig",
]
