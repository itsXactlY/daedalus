"""
Daedalus CLI - Unified command-line interface for Daedalus Agent.

Provides subcommands for:
- daedalus chat          - Interactive chat (same as ./daedalus)
- daedalus gateway       - Run gateway in foreground
- daedalus gateway start - Start gateway service
- daedalus gateway stop  - Stop gateway service  
- daedalus setup         - Interactive setup wizard
- daedalus status        - Show status of all components
- daedalus cron          - Manage cron jobs
"""

# Human-readable distribution version. PEP 440 metadata in
# pyproject.toml normalises this to "0.8.1+daedalus".
__version__ = "0.8.1-Daedalus"
__release_date__ = "2026.8.9"
