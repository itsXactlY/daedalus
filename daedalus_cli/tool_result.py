"""Classifying a tool result so it can be rendered as the right thing.

Why this exists
---------------
Everything a tool returns was being handed to a Markdown renderer. That is
correct for one kind of thing -- the assistant's own prose -- and wrong for
every other kind. A ``ls`` listing, a JSON API response and a stack trace are
not prose, and running them through a Markdown parser produces exactly what
the TUI showed: escaped ``\\n`` sequences printed as literal characters, a
source file reflowed into one unreadable paragraph, and ANSI codes that the
parser treated as text.

So a result has to be classified before it is rendered, and the classifier is
a separate, testable unit. Keeping it out of the block renderer means the
rendering rules can be read in one place and the classification can be tested
without a terminal.

The kinds
---------
``markdown``  the assistant's prose. The only kind a Markdown parser sees.
``code``      source, diffs, listings, stack traces. Real newlines, so it
              belongs in a fenced block where the renderer preserves them.
``data``      JSON. Pretty-printed and fenced, so it is inspectable rather
              than reflowed.
``empty``     nothing worth showing; renders to no rows at all.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

__all__ = ["ResultKind", "ClassifiedResult", "classify_result"]


class ResultKind(str, Enum):
    EMPTY = "empty"
    MARKDOWN = "markdown"
    CODE = "code"
    DATA = "data"


@dataclass(frozen=True)
class ClassifiedResult:
    """What to render, and how."""

    kind: ResultKind
    text: str
    #: fence language for CODE/DATA, empty for MARKDOWN
    language: str = ""


#: A line that looks like source or command output rather than prose. Used only
#: as a tiebreak: if a result is mostly these, it is code even when it has no
#: newline to go on.
_CODEISH = re.compile(
    r"""^(?:
          \d+:\S                      # grep -n / nl output: 53:WIRE_FRAME_MAX
        | [+\-]{1,2}\s                 # diff markers
        | \t                          # indented source
        | \s{4,}\S                     # indented source, spaces
        | [#@]\s
        | [\w./-]*\.\w{1,4}(?::\d+)?\s*$   # a bare path or file:line
    )""",
    re.VERBOSE,
)

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_ESCAPED_NL = re.compile(r"\\n")
_LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".jsx": "jsx", ".rs": "rust", ".go": "go", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".java": "java", ".rb": "ruby", ".sh": "bash",
    ".bash": "bash", ".zsh": "bash", ".json": "json", ".yaml": "yaml",
    ".yml": "yaml", ".toml": "toml", ".md": "markdown", ".html": "html",
    ".css": "css", ".sql": "sql", ".rs": "rust",
}


def _decode_escaped(text: str) -> str:
    """Turn literal ``\\n`` / ``\\t`` sequences into real ones.

    Tool results arrive as JSON string values, so a listing that was three
    lines in the shell comes through as one line containing backslash-n.
    Rendering that as Markdown shows the reader the literal ``\\n``, which is
    how the TUI ended up with ``-rw-r--r-- 1 alca alca 1.8k ...\\n-rw-...``
    printed as prose.

    This is deliberately *not* applied to text that reads as prose. Prose
    legitimately talks about escape sequences ("use ``\\n`` to break a line"),
    and unescaping that would silently corrupt what the model said. So the
    caller decides: only code-shaped results get decoded.
    """
    if "\\n" not in text and "\\t" not in text:
        return text
    return (text.replace("\\r\\n", "\n")
                .replace("\\n", "\n")
                .replace("\\t", "\t"))


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        json.loads(stripped)
        return True
    except Exception:
        return False


def _language_for(text: str) -> str:
    """Guess a fence language from the shape of the content."""
    first = text.lstrip().split("\n", 1)[0]
    if first.startswith(("#!", "#!/")):
        if "python" in first:
            return "python"
        return "bash"
    if first.startswith(("{", "[")):
        return "json"
    if "Traceback (most recent call last)" in text:
        return "python"
    if re.match(r"^\s*(def |class |import |from \w+ import |async def )", first):
        return "python"
    m = re.search(r"([\w./-]+\.\w{1,4})\b", first)
    if m:
        ext = m.group(1)
        dot = ext.rfind(".")
        if dot != -1:
            lang = _LANG_BY_EXT.get(ext[dot:].lower(), "")
            if lang:
                return lang
    if re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE)\b", first, re.I):
        return "sql"
    if re.match(r"^\s*(git|npm|pip|docker|make|cd|ls|grep)\b", first):
        return "bash"
    return ""


#: Signals that a single line is command output rather than prose. Checked
#: before any unescaping, because unescaping is only safe once we know the
#: text is not something the model wrote on purpose.
_OUTPUTISH = re.compile(
    r"""^\s*(?:
          [-+]{1,2}\s
        | [-dDlbcps][-rwxsStT]{9}[+@.]?\s     # ls -l permissions
        | [\w./-]+\.\w{1,4}(?::\d+)?\s
        | [?MADRCU]{1,2}\s+[\w./-]            # git status columns
        | [│|]
        | Traceback \(most recent call last\):
        | [#@]\s
    )""",
    re.VERBOSE,
)


#: First lines that mean "this is source", regardless of indentation.
#: Written without re.VERBOSE: in verbose mode runs of whitespace inside the
#: pattern are ignored, which silently breaks the alternatives that contain
#: literal spaces (e.g. "Traceback (most recent call last):").
_SOURCE_HEAD = re.compile(
    r"^(?:"
    r"\#!/"                                        # shebang
    r"|\#!/usr/bin/env"
    r"|(?:from|import)\s+\w+"
    r"|(?:async\s+)?def\s+\w+\s*[\(:]"
    r"|class\s+\w+\s*[\(:]"
    r"|\w+\s*=\s*\S"                               # assignment
    r"|(?:SELECT|INSERT|UPDATE|DELETE|CREATE)\b"
    r"|Traceback \(most recent call last\):"
    r"|\w+\.\w+\(.*\)"                             # call
    r")"
)


def _looks_like_output(text: str) -> bool:
    """Code-shaped: output, listings, source. Safe to unescape.

    Judged on the whole text, not the first line. A diff starts with ``---``,
    a git status with a space, a source file with an import; requiring the
    first line to carry a marker would classify all of those as prose and send
    them through the reflowing Markdown renderer, which is the bug being fixed.
    """
    stripped = text.strip()
    if not stripped:
        return False

    # Decoded form is what matters: a listing whose newlines are escaped is
    # still a listing once they are real.
    probe = _decode_escaped(stripped)

    if "\\n" in stripped and stripped.count("\\n") >= 2:
        return True

    if _SOURCE_HEAD.match(stripped):
        return True
    if _OUTPUTISH.match(stripped) or _CODEISH.match(stripped):
        return True

    if "\n" in probe.rstrip("\n"):
        head = [ln for ln in probe.split("\n") if ln.strip()][:6]
        if any(_OUTPUTISH.match(ln) or _CODEISH.match(ln) for ln in head):
            return True
        marks = sum(1 for ln in head if ln.lstrip()[:1] in ("-", "+", "@"))
        if marks >= 2:
            return True

    return _looks_like_output_path(stripped)


def classify_result(raw: str, *, tool_name: str = "") -> ClassifiedResult:
    """Decide how a tool result should be rendered.

    Order matters twice over.

    JSON is checked first, because a JSON document is also the envelope a
    result arrives in; unescaping it first would corrupt the string values
    inside it.

    Then prose is ruled out *before* unescaping. A model that writes "use \\n
    to break a line" means it literally, and silently turning that into a line
    break would misreport what was said. Unescaping is only applied once the
    text is known to be command output.
    """
    if raw is None:
        return ClassifiedResult(ResultKind.EMPTY, "")

    text = _ANSI.sub("", raw)

    if _looks_like_json(text):
        try:
            parsed = json.loads(text.strip())
        except Exception:
            parsed = None
        if parsed is not None:
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            # A JSON envelope around a text payload -- {"status": ..., "output":
            # "..."} -- is a wrapper, not the answer. Unwrap it, so the caller
            # classifies what the tool actually produced rather than the
            # bookkeeping around it.
            inner = _unwrap_envelope(parsed)
            if inner is not None and inner != pretty:
                return classify_result(inner, tool_name=tool_name)
            return ClassifiedResult(ResultKind.DATA, pretty, "json")

    if not text.strip():
        return ClassifiedResult(ResultKind.EMPTY, "")

    if not text.strip():
        return ClassifiedResult(ResultKind.EMPTY, "")

    if _looks_like_output(text):
        decoded = _decode_escaped(text)
        if not decoded.strip():
            return ClassifiedResult(ResultKind.EMPTY, "")
        return ClassifiedResult(ResultKind.CODE, decoded.rstrip("\n"),
                                _language_for(decoded))

    # Everything left reads as something the model wrote. Leave its escapes
    # alone: a model that writes "\n" means it.
    stripped = text.strip()
    if "\\n" not in text and "\n" not in text.rstrip("\n"):
        return ClassifiedResult(ResultKind.MARKDOWN, stripped)
    return ClassifiedResult(ResultKind.MARKDOWN, text.strip())


def _unwrap_envelope(parsed) -> str | None:
    """Pull the payload out of a JSON result envelope.

    Tools report ``{"status": "success", "output": "..."}``. Pretty-printing
    that wrapper shows the reader bookkeeping and hides the result, which is
    what made the execute_code output unreadable.
    """
    if not isinstance(parsed, dict):
        return None
    for key in ("output", "stdout", "result", "text", "content", "data"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            # Only unwrap when there is little else of interest in the object.
            others = [k for k in parsed if k != key and parsed[k] not in (None, "", [], {})]
            if len(others) <= 1:
                return value
    return None


def _looks_like_output_path(text: str) -> bool:
    """A lone path, URL or status word: output, not prose."""
    stripped = text.strip()
    if not stripped:
        return False
    if " " not in stripped and ("/" in stripped or "\\" in stripped):
        return True
    if stripped.startswith(("http://", "https://")):
        return True
    return False