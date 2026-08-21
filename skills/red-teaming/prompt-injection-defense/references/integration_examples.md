# Gateway Integration Examples

Code examples for integrating prompt injection defense with Hermes gateway and agents.

## Gateway Pre-Processing Hook

Install in `~/.hermes/hooks/preprocess_gateway_input.py`:

```python
#!/usr/bin/env python3
"""Gateway input preprocessing for injection defense."""

import os
import sys
from pathlib import Path

# Load defense scripts
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
SCRIPTS_DIR = HERMES_HOME / "skills/red-teaming/prompt-injection-defense/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from injection_detector import InjectionDetector, apply_mitigation

detector = InjectionDetector()

def preprocess_input(user_input: str, platform: str, channel_id: str) -> dict:
    """
    Pre-process gateway input before agent handling.
    
    Args:
        user_input: Raw message from platform
        platform: telegram, discord, slack, etc.
        channel_id: Channel identifier for context
    
    Returns:
        Processed input with defense metadata
    """
    # Detect injection
    detection = detector.detect(user_input)
    
    if detection["detected"]:
        # Log the attempt
        log_injection_attempt(user_input, platform, detection)
        
        # Apply mitigation
        sanitized = apply_mitigation(user_input, mode="sanitize")
        
        return {
            "original_input": user_input,
            "processed_input": sanitized,
            "blocked": False,
            "quarantine": detection["confidence"] > 0.9,
            "security_alert": True,
            "confidence": detection["confidence"],
            "category": detection["category"]
        }
    
    return {
        "original_input": user_input,
        "processed_input": user_input,
        "blocked": False,
        "quarantine": False,
        "security_alert": False
    }


def log_injection_attempt(input_text: str, platform: str, detection: dict):
    """Log injection attempts for security review."""
    log_dir = HERMES_HOME / "security" / "injection_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform,
        "input_preview": input_text[:200],
        "detection": detection,
        "session_id": os.environ.get("HERMES_SESSION_ID", "unknown")
    }
    
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

## MCP Response Filtering

Add to MCP server configuration in `config.yaml`:

```yaml
mcp_servers:
  btquant:
    command: "python"
    args: ["mcp-adapter/server.py"]
    security_filter: prompt_injection_defense
    filter_level: strict

  pulse-wurm:
    command: "python"  
    args: ["pulse/server.py"]
    security_filter: prompt_injection_defense
    filter_level: moderate
```

MCP server wrapper:

```python
# mcp-security-wrapper.py
import sys
import os
from injection_detector import InjectionDetector, apply_mitigation

detector = InjectionDetector()

def filter_mcp_response(response: dict) -> dict:
    """Filter MCP tool responses for injection patterns."""
    # Check response content
    content = response.get("content", "")
    
    if "text" in response:
        detection = detector.detect(response["text"])
    elif "candidates" in response:
        # Check pulse search results
        for candidate in response.get("candidates", []):
            if detector.check(candidate.get("content", "")):
                candidate["security_filtered"] = True
                candidate["content"] = apply_mitigation(candidate["content"], mode="sanitize")
    else:
        detection = detector.detect(content)
    
    if detection.get("detected"):
        return {
            "original": response,
            "filtered": apply_mitigation(content),
            "security_flags": detection
        }
    
    return {"original": response, "filtered": response}


# Hook point in MCP handler
def on_tool_response(tool_name: str, response: any) -> any:
    """Hook called after each MCP tool response."""
    if isinstance(response, str):
        detection = detector.detect(response)
        if detection["detected"]:
            return apply_mitigation(response, mode="sanitize")
    return response
```

## Agent Integration (Hermes)

Add to agent configuration:

```python
# In Hermes agent pre-processing
from injection_detector import InjectionDetector, apply_mitigation

def agent_preprocess(state: dict) -> dict:
    """Pre-process agent state before model call."""
    detector = InjectionDetector()
    
    # Check last user message
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            detection = detector.detect(msg.get("content", ""))
            if detection["detected"]:
                msg["content"] = apply_mitigation(msg["content"], mode="sanitize")
                msg["security_processed"] = True
                msg["injection_confidence"] = detection["confidence"]
            break
    
    # Check tool results for poisoning
    tool_results = state.get("tool_results", [])
    for result in tool_results:
        if isinstance(result, str) and detector.check(result):
            result = apply_mitigation(result, mode="sanitize")
    
    return state
```

## BTQuant Trading Agent Protection

```python
# In BTQuant orchestrator or strategy runner
import os
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/red-teaming/prompt-injection-defense/scripts"))
from injection_detector import InjectionDetector

detector = InjectionDetector()

def validate_trading_params(params: dict) -> tuple:
    """
    Validate trading parameters for injection.
    
    Returns:
        (is_valid, sanitized_params, security_flags)
    """
    flags = []
    sanitized = {}
    
    for key, value in params.items():
        if isinstance(value, str):
            detection = detector.detect(value)
            if detection["detected"]:
                flags.append({
                    "param": key,
                    "confidence": detection["confidence"],
                    "category": detection["category"]
                })
                sanitized[key] = apply_mitigation(value)
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    
    return len(flags) == 0, sanitized, flags


# In strategy generation
def generate_strategy(user_prompt: str) -> dict:
    """Generate trading strategy with injection defense."""
    detection = detector.detect(user_prompt)
    
    if detection["detected"]:
        # Log and potentially reject
        if detection["confidence"] > 0.9:
            raise SecurityError("High-confidence injection detected")
        
        user_prompt = apply_mitigation(user_prompt)
    
    return {"prompt": user_prompt, "defense_applied": bool(detection["detected"])}
```

## Pulse-Wurm Content Filtering

```python
# In pulse research pipeline
from injection_detector import InjectionDetector

def filter_search_results(results: list) -> list:
    """Filter pulse search results for injection patterns."""
    detector = InjectionDetector()
    filtered = []
    
    for result in results:
        content = result.get("content", "")
        detection = detector.detect(content)
        
        if detection["detected"]:
            result["security_filtered"] = True
            result["original_content"] = content
            result["content"] = apply_mitigation(content, mode="sanitize")
            result["injection_score"] = detection["confidence"]
        
        filtered.append(result)
    
    return filtered


def run_secured_pulse(topic: str) -> dict:
    """Run pulse research with security filtering."""
    from pulse import pulse_research
    
    # Get raw results
    raw_results = pulse_research(topic=topic)
    
    # Filter for injection
    secure_results = filter_search_results(raw_results.get("candidates", []))
    
    return {
        "topic": topic,
        "candidates": secure_results,
        "security_applied": True
    }
```

## Cron Job: Daily Defense Audit

```python
# scripts/run_defense_audit.py
#!/usr/bin/env python3
"""Daily audit of prompt injection defenses."""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
sys.path.insert(0, str(HERMES_HOME / "skills/red-teaming/prompt-injection-defense/scripts"))

from prompt_injection_tester import run_defensive_tests

def run_audit():
    """Run daily defense audit and report."""
    results = run_defensive_tests(agents=["hermes", "pulse-wurm", "btquant"])
    
    # Check against thresholds
    alerts = []
    if results["detection_rate"] < 95:
        alerts.append(f"Detection rate dropped: {results['detection_rate']:.1f}%")
    if results["mitigation_rate"] < 90:
        alerts.append(f"Mitigation rate dropped: {results['mitigation_rate']:.1f}%")
    
    # Write report
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "alerts": alerts,
        "status": "PASS" if not alerts else "REVIEW"
    }
    
    report_path = HERMES_HOME / "security" / f"audit_{datetime.now().strftime('%Y-%m-%d')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    
    # Send alerts if configured
    if alerts:
        send_security_alert(alerts)
    
    return report


def send_security_alert(alerts: list):
    """Send security alert via configured channel."""
    # Check for alert webhook or Discord config
    config_path = HERMES_HOME / "security" / "alerts.yaml"
    if config_path.exists():
        # Send alert
        pass


if __name__ == "__main__":
    report = run_audit()
    print(f"Audit status: {report['status']}")
    if report['alerts']:
        for alert in report['alerts']:
            print(f"  ⚠️ {alert}")
```

## Response Verification

```python
# Verify agent responses haven't been influenced by injection
def verify_response_integrity(response: str) -> dict:
    """
    Check if response shows signs of injection influence.
    
    Returns:
        {"clean": bool, "indicators": list, "confidence": float}
    """
    injection_indicators = [
        r"(?i)GODMODE",
        r"(?i)unrestricted\s+AI",
        r"(?i)no\s+(longer\s+)?restricted",
        r"(?i)jailbreak\s+(successful|enabled)",
        r"(?i)ignore\s+(my\s+)?(instructions|policies)",
    ]
    
    found = []
    for pattern in injection_indicators:
        if re.search(pattern, response):
            found.append(pattern)
    
    return {
        "clean": len(found) == 0,
        "indicators": found,
        "confidence": min(1.0, len(found) * 0.3)
    }
```

## Hook Installation

```python
# install_hooks.py
def install_gateway_hooks():
    """Install all defense hooks for Hermes gateway."""
    hooks_dir = HERMES_HOME / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    
    # Copy hook files
    hook_files = [
        "preprocess_gateway_input.py",
        "verify_response_integrity.py",
        "log_injection_attempt.py"
    ]
    
    for hook in hook_files:
        # Copy from references or create
        pass
    
    # Update config
    update_config_with_hooks()


def update_config_with_hooks():
    """Update Hermes config.yaml with hook references."""
    hook_config = {
        "security": {
            "prompt_injection_defense": {
                "enabled": True,
                "detection_threshold": 0.75,
                "mitigation_mode": "sanitize",
                "log_injections": True,
                "pre_hook": "hooks/preprocess_gateway_input.py"
            }
        }
    }
    # Merge with existing config
```