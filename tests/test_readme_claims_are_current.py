import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"


def _readme() -> str:
    if not README.exists():
        pytest.skip("README.md is not shipped in this tree")
    return README.read_text(encoding="utf-8")


class TestTheReadmeStaysHonest:
    """The README makes counted claims. Counts drift; claims should not.

    Numbers that are measured elsewhere (a live pod, a benchmark run) cannot be
    checked here. What can be checked is anything the repository itself knows.
    """

    def test_the_shipped_skill_count_matches_the_tree(self):
        claimed = re.search(r"(\d+) curated skills across (\d+) packs", _readme())
        assert claimed, "the skills claim disappeared from the README"
        skills = len(list((REPO / "skills").rglob("SKILL.md")))
        packs = len([p for p in (REPO / "skills").iterdir() if p.is_dir()])
        assert int(claimed.group(1)) == skills
        assert int(claimed.group(2)) == packs

    def test_relative_links_resolve(self):
        broken = [
            target for target in re.findall(r"\]\((?!https?:)([^)]+)\)", _readme())
            if not (REPO / target.split("#")[0]).exists()
        ]
        assert not broken, f"dead relative links: {broken}"

    def test_code_fences_are_balanced(self):
        assert _readme().count("```") % 2 == 0

    def test_it_states_the_memory_dependency(self):
        text = _readme()
        assert "mazemaker.online" in text
        assert "amnesiac" in text.lower()

    def test_it_is_not_an_installation_manual(self):
        """The README argues a position; the install is one paragraph of it."""
        text = _readme().lower()
        install_section = text.split("## getting it")[-1].split("##")[0]
        # Room for the section plus one pointer at the all-in-one alternative;
        # not room for a step-by-step. Steps belong in `stack.sh doctor`.
        assert len(install_section) < 1200, "the install section grew into a tutorial"
        assert "```" not in install_section, "no command blocks to copy-paste from"
