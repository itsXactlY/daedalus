"""Tests for agent/skill_router.py — deterministic skill auto-routing.

Hermetic: the catalog source is monkeypatched to a tiny synthetic tree so the
tests never depend on the operator's real 326-skill collection or on HOME.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import agent.skill_router as router
from agent.skill_router import (
    _tokens,
    already_loaded_skill_names,
    build_skill_route_block,
    route_skills,
    score_skill,
)

# A tiny synthetic catalog to keep tests hermetic (no dependency on the
# operator's real 326-skill tree).
FAKE_CATALOG = [
    {
        "skill_name": "game-loot-economy",
        "category": "gaming",
        "frontmatter_name": "game-loot-economy",
        "description": "Build, audit, and repair game economy loot table configs.",
    },
    {
        "skill_name": "podman-quadlet-ops",
        "category": "devops",
        "frontmatter_name": "podman-quadlet-ops",
        "description": "Audit Podman Quadlet stacks: OOM, drop-ins, reboot cascades.",
    },
    {
        "skill_name": "daedalus-harness-audit",
        "category": "autonomous-ai-agents",
        "frontmatter_name": "daedalus-harness-audit",
        "description": "Use when auditing the daedalus harness for flaws.",
    },
    {
        "skill_name": "unsloth",
        "category": "mlops/training",
        "frontmatter_name": "unsloth",
        "description": "Expert guidance for fast fine-tuning with Unsloth.",
    },
]


@pytest.fixture(autouse=True)
def _fake_catalog(monkeypatch):
    monkeypatch.setattr(router, "load_skill_catalog", lambda *a, **k: FAKE_CATALOG)


def test_tokens_strips_stopwords():
    assert "the" not in _tokens("the quick audit")
    assert "audit" in _tokens("the quick audit")
    assert _tokens("") == []


def test_score_skill_name_boost():
    q = _tokens("game loot")
    entry = FAKE_CATALOG[0]
    name_score = score_skill(q, entry)
    # A name hit (5x) should beat a description-only hit for the same token.
    desc_only = {
        "skill_name": "zzz",
        "category": "",
        "frontmatter_name": "zzz",
        "description": "game loot repair",
    }
    assert name_score > score_skill(q, desc_only)


def test_route_skills_finds_exact_match():
    q = "fix the dayz server loot economy"
    routed = route_skills(q, top_n=5, min_score=0.1)
    names = [e["skill_name"] for e in routed]
    assert "game-loot-economy" in names
    # Top pick is deterministic and best-scoring.
    assert routed[0]["skill_name"] == "game-loot-economy"


def test_route_skills_empty_message_no_routing():
    assert route_skills("good morning", top_n=5, min_score=0.1) == []
    assert route_skills("", top_n=5) == []
    assert route_skills("ok", top_n=5, min_score=0.1) == []


def test_route_skills_respects_top_n():
    routed = route_skills("podman quadlet stack audit", top_n=2, min_score=0.1)
    assert len(routed) <= 2
    assert all("_score" in e for e in routed)
    assert all(e["_score"] >= 0.1 for e in routed)


def test_route_skills_sorted_desc():
    routed = route_skills("podman quadlet stack audit", top_n=5, min_score=0.1)
    scores = [e["_score"] for e in routed]
    assert scores == sorted(scores, reverse=True)


def test_build_route_block_empty_when_no_match():
    assert build_skill_route_block("good morning", top_n=3, min_score=0.1) == ""


def test_build_route_block_mentions_skill_view():
    block = build_skill_route_block("audit the daedalus harness", top_n=3, min_score=0.1)
    assert "daedalus-harness-audit" in block
    assert "skill_view" in block


def test_already_loaded_skill_names_detects_bundle_marker():
    msg = "Skills loaded: podman-quadlet-ops, game-loot-economy\n\nBundle content..."
    assert already_loaded_skill_names(msg) == {"podman-quadlet-ops", "game-loot-economy"}


def test_already_loaded_skill_names_detects_single_skill_marker():
    msg = '[SYSTEM: The user has invoked the "daedalus-harness-audit" skill, indicating...]'
    assert already_loaded_skill_names(msg) == {"daedalus-harness-audit"}


def test_already_loaded_skill_names_empty_when_no_marker():
    assert already_loaded_skill_names("just a normal question about podman") == set()


def test_route_skills_excludes_given_names():
    with_exclude = route_skills(
        "podman quadlet stack audit", top_n=5, min_score=0.1,
        exclude_names={"podman-quadlet-ops"},
    )
    assert all(e["skill_name"] != "podman-quadlet-ops" for e in with_exclude)

    without_exclude = route_skills("podman quadlet stack audit", top_n=5, min_score=0.1)
    assert any(e["skill_name"] == "podman-quadlet-ops" for e in without_exclude)


def test_build_route_block_auto_excludes_already_loaded_bundle_skill():
    # The bundle marker for podman-quadlet-ops is embedded in the same message
    # that would otherwise route straight back to it -- the router must not
    # re-suggest content already present in this exact API-bound message.
    msg = (
        "Skills loaded: podman-quadlet-ops\n\n"
        "Audit this podman quadlet stack for OOM issues."
    )
    block = build_skill_route_block(msg, top_n=5, min_score=0.1)
    assert "podman-quadlet-ops" not in block
