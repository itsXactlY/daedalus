"""Focused tests for agent/skill_bundles.py — YAML-defined skill bundles.

Covers the four port-critical behaviors: empty dir → {}, save + reload,
command-key resolution, and the bundle-wins-over-skill conflict rule.
"""

import os
from pathlib import Path

import pytest

from agent.skill_bundles import (
    get_bundle,
    get_skill_bundles,
    reload_bundles,
    resolve_bundle_command_key,
    save_bundle,
    scan_bundles,
)


def _make_bundle_yaml(
    bundles_dir: Path, slug: str, skills: list[str],
    description: str = "", name: str | None = None,
) -> Path:
    bundles_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"name: {name or slug}")
    if description:
        lines.append(f"description: {description}")
    lines.append("skills:")
    for s in skills:
        lines.append(f"  - {s}")
    path = bundles_dir / f"{slug}.yaml"
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def bundles_env(tmp_path, monkeypatch):
    """Isolated bundles dir + skills dir."""
    bundles_dir = tmp_path / "skill-bundles"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setenv("DAEDALUS_BUNDLES_DIR", str(bundles_dir))
    # Patch SKILLS_DIR so skill loading hits our temp tree.
    import tools.skills_tool as skills_tool_module
    monkeypatch.setattr(skills_tool_module, "SKILLS_DIR", skills_dir)
    # Reset module-level cache between tests.
    import agent.skill_bundles as mod
    mod._bundles_cache = {}
    mod._bundles_cache_mtime = None
    return bundles_dir, skills_dir


class TestGetSkillBundles:
    def test_empty_dir_returns_empty(self, bundles_env):
        """No bundle files → get_skill_bundles() returns {} without crashing."""
        assert get_skill_bundles() == {}

    def test_returns_cache(self, bundles_env):
        bundles_dir, _ = bundles_env
        _make_bundle_yaml(bundles_dir, "a", ["s1"])
        first = get_skill_bundles()
        second = get_skill_bundles()
        assert first == second
        assert "/a" in first


class TestSaveAndReload:
    def test_save_bundle_and_reload_finds_it(self, bundles_env):
        """save_bundle writes a file and reload picks it back up."""
        bundles_dir, _ = bundles_env
        path = save_bundle("test-bundle", ["s1", "s2"], description="d")
        assert path.exists()
        assert path.parent == bundles_dir

        info = get_bundle("test-bundle")
        assert info is not None
        assert info["skills"] == ["s1", "s2"]

        # reload_bundles diffs the in-memory cache against a fresh scan.
        # save_bundle already refreshed the cache, so write a second bundle
        # directly (bypassing the helper) to exercise the "added" path.
        _make_bundle_yaml(bundles_dir, "raw", ["s3"])
        diff = reload_bundles()
        added_names = {e["name"] for e in diff["added"]}
        assert "raw" in added_names
        assert diff["total"] == 2

    def test_save_overwrite(self, bundles_env):
        """save_bundle refuses to clobber unless overwrite=True."""
        save_bundle("dup", ["s1"])
        with pytest.raises(FileExistsError):
            save_bundle("dup", ["s2"])
        save_bundle("dup", ["s2"], overwrite=True)
        assert get_bundle("dup")["skills"] == ["s2"]


class TestResolveBundleCommandKey:
    def test_maps_name_to_slash_key(self, bundles_env):
        bundles_dir, _ = bundles_env
        _make_bundle_yaml(bundles_dir, "my-bundle", ["s1"])
        scan_bundles()
        assert resolve_bundle_command_key("my-bundle") == "/my-bundle"

    def test_underscore_treated_as_hyphen(self, bundles_env):
        bundles_dir, _ = bundles_env
        _make_bundle_yaml(bundles_dir, "my-bundle", ["s1"])
        scan_bundles()
        assert resolve_bundle_command_key("my_bundle") == "/my-bundle"

    def test_unknown_and_empty(self, bundles_env):
        scan_bundles()
        assert resolve_bundle_command_key("missing") is None
        assert resolve_bundle_command_key("") is None


class TestBundleWinsOverSkill:
    def test_bundle_shadows_skill_in_completion(self, bundles_env):
        """A bundle and a skill sharing a slug: only the bundle is offered.

        Dispatch order in cli.py checks bundles before skills; the completer
        mirrors that by skipping a skill command that a bundle shadows.
        """
        bundles_dir, _ = bundles_env
        _make_bundle_yaml(bundles_dir, "demo", ["demo-skill"])

        from daedalus_cli.commands import SlashCommandCompleter
        from prompt_toolkit.document import Document

        # A same-named skill, provided directly so we don't perturb the
        # process-global skill-command cache.
        skill_provider = lambda: {"/demo": {"name": "demo", "description": "a skill"}}
        completer = SlashCommandCompleter(
            skill_commands_provider=skill_provider,
            skill_bundles_provider=lambda: get_skill_bundles(),
        )

        completions = list(completer.get_completions(Document("/demo"), None))
        # display is a FormattedText; match on the underlying command text.
        demo = [c for c in completions if "/demo" in str(c.display)]
        assert len(demo) == 1
        meta = str(demo[0].display_meta or "")
        # Bundle marker, not the skill's lightning-bolt marker.
        assert "▣" in meta or "skills" in meta
        assert not meta.startswith("⚡")

    def test_resolves_bundle_key_when_skill_also_exists(self, bundles_env, monkeypatch):
        """Both a skill and a bundle use /demo — the bundle key resolves."""
        bundles_dir, skills_dir = bundles_env
        skill_dir = skills_dir / "demo"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo\ndescription: demo skill\n---\n\n# demo\n\nBody.\n"
        )
        _make_bundle_yaml(bundles_dir, "demo", ["demo"])

        # Repopulate the skill cache against the temp skills dir.
        from agent import skill_commands
        skill_commands.scan_skill_commands()
        assert "/demo" in skill_commands.get_skill_commands()
        assert "/demo" in get_skill_bundles()
        assert resolve_bundle_command_key("demo") == "/demo"
