"""Tests for tools/skills_selfaudit.py — the collection-level, LLM-free audit.

Every check gets a fixture that must trip it. A collection check that never
fires on real data is indistinguishable from a broken one, and the hub checks in
particular reported zero findings across 38 hubs on first run — that is exactly
the result a silently broken regex also produces.
"""

import textwrap

import pytest

from tools.skills_selfaudit import (
    ERROR,
    WARNING,
    audit_collection,
    check_hub_index,
    collect_hub_members,
    collect_tool_calls,
    discover_skills,
    harvest_tool_names,
    parse_manifest_names,
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


def _skill(root, rel, name, body="Body text.\n", extra=""):
    # Built flush-left on purpose. Interpolating `body` into an indented
    # triple-quoted template and dedupting afterwards leaves the body's first
    # line indented and the rest flush, so textwrap.dedent finds no common
    # prefix and silently keeps the whole template indented — which then fails
    # to parse as frontmatter. Dedup the shell, not the result.
    text = (
        "---\n"
        f"name: {name}\n"
        "description: A skill used by the self-audit test suite.\n"
        f"{extra}"
        "---\n\n"
        f"# {name}\n\n"
        f"{body}"
    )
    return _write(root / rel / "SKILL.md", text)


# --- discovery -------------------------------------------------------------


def test_discover_skips_quarantine_and_caches(tmp_path):
    _skill(tmp_path, "cat/alpha", "alpha")
    _skill(tmp_path, "cat/references/beta", "beta")
    _skill(tmp_path, "_consolidate/old", "old")
    _skill(tmp_path, "index-cache/cached", "cached")
    _skill(tmp_path, ".curator_backups/x", "backuped")

    found = {p.parent.name for p in discover_skills(tmp_path)}

    assert found == {"alpha", "beta"}


# --- hub <-> member index --------------------------------------------------


def test_collect_members_reads_bold_bullets():
    body = "## Members\n\n- **one** — first\n- **two** — second\n\n## Notes\n- **nope** — x\n"
    assert collect_hub_members(body) == ["one", "two"]


def test_hub_member_missing_is_an_error(tmp_path):
    _skill(tmp_path, "cat", "cat", body="## Members\n\n- **ghost** — not on disk\n")
    report = audit_collection(tmp_path)
    rules = {(f.rule, f.severity) for f in report.findings}
    assert ("hub-member-missing", ERROR) in rules
    assert report.has_errors


def test_hub_member_unlisted_is_a_warning(tmp_path):
    _skill(tmp_path, "cat", "cat", body="## Members\n\n- **alpha** — listed\n")
    _skill(tmp_path, "cat/references/alpha", "alpha")
    _skill(tmp_path, "cat/references/beta", "beta")

    report = audit_collection(tmp_path)

    msgs = [f.message for f in report.findings if f.rule == "hub-member-unlisted"]
    assert len(msgs) == 1 and "beta" in msgs[0]
    assert not report.has_errors


def test_hub_count_drift_detected(tmp_path):
    _skill(
        tmp_path,
        "cat",
        "cat",
        body="This hub aggregates 7 member skills under references/.\n\n## Members\n\n- **alpha** — x\n",
    )
    _skill(tmp_path, "cat/references/alpha", "alpha")

    report = audit_collection(tmp_path)

    assert any(f.rule == "hub-count-drift" for f in report.findings)


def test_hub_without_member_list_is_flagged(tmp_path):
    _skill(tmp_path, "cat", "cat", body="No list here.\n")
    _skill(tmp_path, "cat/references/alpha", "alpha")

    report = audit_collection(tmp_path)

    assert any(f.rule == "hub-no-member-list" for f in report.findings)


def test_healthy_hub_reports_nothing(tmp_path):
    _skill(
        tmp_path,
        "cat",
        "cat",
        body="This hub aggregates 1 member skills under references/.\n\n## Members\n\n- **alpha** — x\n",
    )
    _skill(tmp_path, "cat/references/alpha", "alpha")

    report = audit_collection(tmp_path)

    assert report.findings == []


# --- duplicate names -------------------------------------------------------


def test_duplicate_name_across_hubs_is_an_error(tmp_path):
    _skill(tmp_path, "one/skill", "twin")
    _skill(tmp_path, "two/skill", "twin")

    report = audit_collection(tmp_path)

    dupes = [f for f in report.findings if f.rule == "duplicate-skill-name"]
    assert len(dupes) == 1 and dupes[0].severity == ERROR


# --- tool surface ----------------------------------------------------------


def test_harvest_finds_schema_names_and_methods(tmp_path):
    _write(
        tmp_path / "tools/browser_tool.py",
        '''\
        SCHEMAS = [{"name": "browser_navigate"}, {"name": "browser_click"}]

        def browser_snapshot():
            pass
        ''',
    )
    _write(
        tmp_path / "plugins/memory/__init__.py",
        """\
        class Registry:
            def register_memory_provider(self, provider):
                pass
        """,
    )

    names = harvest_tool_names(tmp_path)

    assert "browser_navigate" in names
    assert "register_memory_provider" in names, "methods count as tool surface"


def test_collect_tool_calls_reads_calls_and_table_cells():
    body = (
        "Call `browser_navigate(url=x)` then check the table.\n"
        "| `browser_click` | clicks |\n"
        "| plain text | not a tool |\n"
        "prose mention of search_files without a paren\n"
    )
    assert collect_tool_calls(body) == {"browser_navigate", "browser_click"}


def test_tool_drift_flags_a_near_miss(tmp_path):
    _write(
        tmp_path / "tools/browser_tool.py",
        'SCHEMAS = [{"name": "browser_navigate"}]\n',
    )
    _skill(tmp_path, "cat", "cat", body="Run `browser_navigat(url=x)` first.\n")

    report = audit_collection(tmp_path, harness_root=tmp_path)

    drift = [f for f in report.findings if f.rule == "tool-reference-drift"]
    assert len(drift) == 1
    assert "browser_navigate" in drift[0].message


def test_foreign_api_is_not_drift(tmp_path):
    """`background(` must not be reported just because `is_background` exists."""
    _write(tmp_path / "tools/x.py", "def is_background():\n    pass\n")
    _skill(tmp_path, "cat", "cat", body="In p5: `background(200)` and `fill(0)`.\n")

    report = audit_collection(tmp_path, harness_root=tmp_path)

    assert not [f for f in report.findings if f.rule == "tool-reference-drift"]


def test_known_tool_call_is_clean(tmp_path):
    _write(tmp_path / "tools/browser_tool.py", 'SCHEMAS = [{"name": "browser_navigate"}]\n')
    _skill(tmp_path, "cat", "cat", body="Run `browser_navigate(url=x)`.\n")

    report = audit_collection(tmp_path, harness_root=tmp_path)

    assert not [f for f in report.findings if f.rule == "tool-reference-drift"]


# --- manifest --------------------------------------------------------------


def test_parse_manifest_names_reads_report_format(tmp_path):
    manifest = _write(
        tmp_path / "manifest.txt",
        """\
        == (uncategorized) ==
          alpha  [100b, 0 refs]  First skill
          beta  [200b, 3 refs]  Second skill

        == other ==
          gamma  [50b, 1 refs]  Third
        """,
    )
    assert parse_manifest_names(manifest) == {"alpha", "beta", "gamma"}


def test_manifest_drift_reports_added_and_removed(tmp_path):
    _skill(tmp_path, "cat/alpha", "alpha")
    _write(
        tmp_path / ".audit/manifest.txt",
        """\
        == (uncategorized) ==
          alpha  [100b, 0 refs]  kept
          ghost  [100b, 0 refs]  deleted since
        """,
    )

    report = audit_collection(tmp_path, manifest=tmp_path / ".audit/manifest.txt")

    removed = [f for f in report.findings if f.rule == "manifest-drift-removed"]
    assert len(removed) == 1 and "ghost" in removed[0].message


def test_unreadable_manifest_is_not_thousands_of_phantoms(tmp_path):
    _skill(tmp_path, "cat/alpha", "alpha")
    _write(tmp_path / ".audit/manifest.txt", "some entirely different format\n")

    report = audit_collection(tmp_path, manifest=tmp_path / ".audit/manifest.txt")

    assert any(f.rule == "manifest-unreadable" for f in report.findings)
    assert not [f for f in report.findings if f.rule == "manifest-drift-removed"]


# --- report shape ----------------------------------------------------------


def test_missing_root_is_an_error_not_a_crash(tmp_path):
    report = audit_collection(tmp_path / "nope")

    assert report.has_errors
    assert report.findings[0].rule == "skills-root-missing"


def test_json_output_is_machine_readable(tmp_path):
    import json

    _skill(tmp_path, "cat", "cat", body="## Members\n\n- **ghost** — x\n")
    report = audit_collection(tmp_path)

    payload = json.loads(report.to_json())

    assert payload["errors"] == 1
    assert payload["by_rule"]["hub-member-missing"] == 1


def test_audit_is_deterministic(tmp_path):
    """Same tree in, same report out — the property that makes it a gate."""
    _skill(tmp_path, "cat", "cat", body="## Members\n\n- **ghost** — x\n")
    _skill(tmp_path, "cat/references/alpha", "alpha")

    first = audit_collection(tmp_path).to_json()
    second = audit_collection(tmp_path).to_json()

    assert first == second
