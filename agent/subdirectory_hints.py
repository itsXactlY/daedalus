"""Progressive subdirectory hint discovery.

As the agent navigates into subdirectories via tool calls (read_file, terminal,
search_files, etc.), this module discovers and loads project context files
(AGENTS.md, CLAUDE.md, .cursorrules) from those directories.  Discovered hints
are appended to the tool result so the model gets relevant context at the moment
it starts working in a new area of the codebase.

This complements the startup context loading in ``prompt_builder.py`` which only
loads from the CWD.  Subdirectory hints are discovered lazily and injected into
the conversation without modifying the system prompt (preserving prompt caching).

Inspired by Block/goose's SubdirectoryHintTracker.
"""

import logging
import os
import shlex
from pathlib import Path
from typing import Dict, Any, Optional, Set

from agent.prompt_builder import _scan_context_content

logger = logging.getLogger(__name__)

_HINT_FILENAMES = [
    "AGENTS.md", "agents.md",
    "CLAUDE.md", "claude.md",
    ".cursorrules",
]

_MAX_HINT_CHARS = 8_000

_PATH_ARG_KEYS = {"path", "file_path", "workdir"}

_COMMAND_TOOLS = {"terminal"}

_MAX_ANCESTOR_WALK = 5

class SubdirectoryHintTracker:
    """Track which directories the agent visits and load hints on first access.

    Usage::

        tracker = SubdirectoryHintTracker(working_dir="/path/to/project")

        # After each tool call:
        hints = tracker.check_tool_call("read_file", {"path": "backend/src/main.py"})
        if hints:
            tool_result += hints  # append to the tool result string
    """

    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = Path(working_dir or os.getcwd()).resolve()
        self._loaded_dirs: Set[Path] = set()
        self._loaded_dirs.add(self.working_dir)

    def check_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Optional[str]:
        """Check tool call arguments for new directories and load any hint files.

        Returns formatted hint text to append to the tool result, or None.
        """
        dirs = self._extract_directories(tool_name, tool_args)
        if not dirs:
            return None

        all_hints = []
        for d in dirs:
            hints = self._load_hints_for_directory(d)
            if hints:
                all_hints.append(hints)

        if not all_hints:
            return None

        return "\n\n" + "\n\n".join(all_hints)

    def _extract_directories(
        self, tool_name: str, args: Dict[str, Any]
    ) -> list:
        """Extract directory paths from tool call arguments."""
        candidates: Set[Path] = set()

        for key in _PATH_ARG_KEYS:
            val = args.get(key)
            if isinstance(val, str) and val.strip():
                self._add_path_candidate(val, candidates)

        if tool_name in _COMMAND_TOOLS:
            cmd = args.get("command", "")
            if isinstance(cmd, str):
                self._extract_paths_from_command(cmd, candidates)

        return list(candidates)

    def _add_path_candidate(self, raw_path: str, candidates: Set[Path]):
        """Resolve a raw path and add its directory + ancestors to candidates.

        Walks up from the resolved directory toward the filesystem root,
        stopping at the first directory already in ``_loaded_dirs`` (or after
        ``_MAX_ANCESTOR_WALK`` levels).  This ensures that reading
        ``project/src/main.py`` discovers ``project/AGENTS.md`` even when
        ``project/src/`` has no hint files of its own.
        """
        try:
            p = Path(raw_path).expanduser()
            if not p.is_absolute():
                p = self.working_dir / p
            p = p.resolve()
            if p.suffix or (p.exists() and p.is_file()):
                p = p.parent
            for _ in range(_MAX_ANCESTOR_WALK):
                if p in self._loaded_dirs:
                    break
                if self._is_valid_subdir(p):
                    candidates.add(p)
                parent = p.parent
                if parent == p:
                    break
                p = parent
        except (OSError, ValueError):
            pass

    def _extract_paths_from_command(self, cmd: str, candidates: Set[Path]):
        """Extract path-like tokens from a shell command string."""
        try:
            tokens = shlex.split(cmd)
        except ValueError:
            tokens = cmd.split()

        for token in tokens:
            if token.startswith("-"):
                continue
            if "/" not in token and "." not in token:
                continue
            if token.startswith(("http://", "https://", "git@")):
                continue
            self._add_path_candidate(token, candidates)

    def _is_valid_subdir(self, path: Path) -> bool:
        """Check if path is a valid directory to scan for hints."""
        if not path.is_dir():
            return False
        if path in self._loaded_dirs:
            return False
        return True

    def _load_hints_for_directory(self, directory: Path) -> Optional[str]:
        """Load hint files from a directory. Returns formatted text or None."""
        self._loaded_dirs.add(directory)

        found_hints = []
        for filename in _HINT_FILENAMES:
            hint_path = directory / filename
            if not hint_path.is_file():
                continue
            try:
                content = hint_path.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                content = _scan_context_content(content, filename)
                if len(content) > _MAX_HINT_CHARS:
                    content = (
                        content[:_MAX_HINT_CHARS]
                        + f"\n\n[...truncated {filename}: {len(content):,} chars total]"
                    )
                rel_path = str(hint_path)
                try:
                    rel_path = str(hint_path.relative_to(self.working_dir))
                except ValueError:
                    try:
                        rel_path = str(hint_path.relative_to(Path.home()))
                        rel_path = "~/" + rel_path
                    except ValueError:
                        pass
                found_hints.append((rel_path, content))
                break
            except Exception as exc:
                logger.debug("Could not read %s: %s", hint_path, exc)

        if not found_hints:
            return None

        sections = []
        for rel_path, content in found_hints:
            sections.append(
                f"[Subdirectory context discovered: {rel_path}]\n{content}"
            )

        logger.debug(
            "Loaded subdirectory hints from %s: %s",
            directory,
            [h[0] for h in found_hints],
        )
        return "\n\n".join(sections)
