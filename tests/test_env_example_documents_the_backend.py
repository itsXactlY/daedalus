from pathlib import Path

import pytest


def _env_example() -> str:
    root = Path(__file__).resolve().parent.parent
    path = root / ".env.example"
    if not path.exists():
        pytest.skip(".env.example is not shipped in this tree")
    return path.read_text(encoding="utf-8")


class TestTheSampleEnvExplainsTheMemoryDependency:
    """The harness does not carry its own history.

    Someone installing it without a memory backend gets an agent engineered to
    forget with nothing remembering for it. That has to be stated where they
    will actually read it, not discovered on day three.
    """

    def test_it_names_the_backend_and_where_to_get_it(self):
        text = _env_example()
        assert "Mazemaker" in text
        assert "mazemaker.online" in text

    def test_it_states_the_consequence_of_running_without_one(self):
        text = _env_example().lower()
        assert "amnesiac" in text or "amnesia" in text

    def test_it_documents_the_variables_the_code_actually_reads(self):
        text = _env_example()
        for var in ("MM_WONDERLAND_URL", "MM_NATIVE_TOOLS"):
            assert var in text

    def test_it_points_at_the_config_keys_that_matter(self):
        text = _env_example()
        for key in ("memory.provider", "tool_search.always_load",
                    "compression.max_tokens"):
            assert key in text

    def test_every_documented_mm_variable_exists_in_the_code(self):
        import re

        root = Path(__file__).resolve().parent.parent
        documented = set(re.findall(r"\bMM_[A-Z0-9_]+\b", _env_example()))
        source = ""
        for path in (root / "plugins" / "memory" / "mazemaker").rglob("*.py"):
            source += path.read_text(encoding="utf-8", errors="replace")
        for var in documented:
            assert var in source, f"{var} is documented but never read"
