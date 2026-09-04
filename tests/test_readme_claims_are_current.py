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

    def test_every_documented_subcommand_exists(self):
        """A README naming a command the CLI does not have is worse than one
        naming none: the reader trusts it and gets an error.

        The stack lifecycle moved from scripts/stack.sh into `daedalus doctor`,
        so the parser — not the shim that forwards to it — is what the README
        is checked against.
        """
        import argparse
        import re

        section = _readme().split("## Getting it")[-1].split("\n## ")[0]
        try:
            from daedalus_cli.stack import register_cli
        except Exception:
            pytest.skip("daedalus_cli.stack is not importable in this tree")

        parser = argparse.ArgumentParser()
        register_cli(parser)
        implemented = set()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                implemented |= set(action.choices)

        documented = set(re.findall(r"`daedalus doctor ([a-z]+)`", section))
        documented |= set(re.findall(r"`([a-z]+)`", section)) - {
            "install", "sh", "daedalus", "doctor",
        }
        invented = documented - implemented
        assert not invented, f"README names subcommands daedalus doctor does not have: {sorted(invented)}"

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
        """The README argues a position. It may name the interface, not teach it.

        Length is a bad proxy — naming eight subcommands is documentation, not a
        tutorial. What makes a section a manual is transcribed command lines
        someone can lift wholesale, so that is what this checks.
        """
        import re

        text = _readme()
        section = text.split("## Getting it")[-1].split("\n## ")[0]
        assert "```" not in section, "no fenced command blocks in the install section"
        prompts = re.findall(r"^\s*[$>#]\s+\S", section, re.M)
        assert not prompts, f"shell-prompt lines belong in the tool, not here: {prompts}"
        # Flags carry the copy-paste risk: a reader lifting `--kv-stream-stage-mib
        # 2048` gets a number tuned for one specific 16 GB card.
        flags = re.findall(r"(?<![\w-])--[a-z][a-z-]{3,}", section)
        assert not flags, f"tuned flags do not belong in a README: {sorted(set(flags))}"
