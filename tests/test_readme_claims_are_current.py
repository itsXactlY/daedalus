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
        # A pack is a directory a human wrote something into: every one of them
        # carries a SKILL.md or a DESCRIPTION.md. Counting bare directories
        # instead let the generated skills/index-cache — four JSON index files,
        # untracked, present only in an installed tree — pass as a 24th pack,
        # so this claim was true where the cache existed and false in a clean
        # checkout of the same commit.
        packs = len([
            p for p in (REPO / "skills").iterdir()
            if p.is_dir() and any(p.rglob("*.md"))
        ])
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


class TestTheTunedNumbersMatchTheShippedDefaults:
    """The README's "why this number" table is the part people copy.

    It rotted silently: it advertised compaction at 116,000 long after the
    real trigger had moved to 64,225, and described a CPU helper model and a
    second inference server that the shipped stack.conf no longer starts.
    Nothing checked it, because the existing claims tests cover the skill
    count and the subcommand list but not the numbers.

    Every value below is one `daedalus doctor` actually launches with, read
    out of stack.py's DEFAULT_CONF rather than restated here.
    """

    @staticmethod
    def _readme():
        import pathlib
        return pathlib.Path(__file__).resolve().parents[1].joinpath("README.md").read_text()

    @staticmethod
    def _default_conf_value(key):
        import re
        from daedalus_cli.stack import DEFAULT_CONF
        m = re.search(rf'^{key}=("?)([^"\n#]+)\1', DEFAULT_CONF, re.M)
        assert m, f"{key} not found in DEFAULT_CONF"
        return m.group(2).strip()

    def test_kv_pool_matches(self):
        pool = self._default_conf_value("MAIN_KV_POOL")
        assert f"KV pool {pool} MB" in self._readme(), (
            f"README's KV pool row disagrees with DEFAULT_CONF ({pool})"
        )

    def test_context_size_matches(self):
        ctx = int(self._default_conf_value("MAIN_CTX"))
        assert f"context {ctx:,}" in self._readme(), (
            f"README's context row disagrees with DEFAULT_CONF ({ctx:,})"
        )

    def test_thinking_budget_matches(self):
        budget = int(self._default_conf_value("MAIN_REASONING_BUDGET"))
        assert f"thinking budget {budget:,}" in self._readme()

    def test_cache_quant_claim_matches(self):
        ctk = self._default_conf_value("MAIN_CTK")
        ctv = self._default_conf_value("MAIN_CTV")
        assert f"KV cache {ctk} / {ctv}" in self._readme(), (
            f"README's cache-quant row disagrees with DEFAULT_CONF ({ctk}/{ctv})"
        )

    def test_it_does_not_advertise_a_second_inference_server(self):
        """AUX_PORT == MAIN_PORT in the shipped conf, and `start` explicitly
        does not launch a second process for it -- the background role is a
        slot on the main server. The README described two servers and a
        1.7B CPU helper for a long time after that stopped being true."""
        readme = self._readme()
        for stale in ("two AI servers", "Two inference servers", "both servers"):
            assert stale not in readme, f"README still claims: {stale!r}"

    def test_the_compaction_row_shows_a_capped_minimum(self):
        """The trigger is min(threshold * ctx, max_tokens), and the cap binds
        above ~134k context -- the reason a bigger window buys almost nothing.
        Stating a bare number invites exactly the drift that happened."""
        readme = self._readme()
        assert "compaction at" in readme
        assert "66,000" in readme, "the cap that actually binds is not stated"
