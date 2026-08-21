"""Gateway dispatch tests for skill bundles.

The gateway slash-command handler in gateway/run.py checks skill bundles
BEFORE individual skills (mirroring cli.py's elif ordering), so a bundle
whose slug shadows a skill wins. These tests exercise the three dispatch
outcomes:

(a) a bundle command resolves and its invocation message is sent
(b) a skill sharing the bundle's name is shadowed (bundle wins)
(c) a non-matching command falls through to the skill path unchanged
(d) a bundle with no loadable members returns a clear guidance message
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    return runner


def _monkeypatch_skill_path(monkeypatch, commands):
    """Point the gateway's skill-command import targets at a fake scan.

    ``commands`` maps a /slug key to a skill-info dict, so the per-platform
    disabled check in the dispatch can read a ``name`` without touching the
    real skills directory or config.
    """
    monkeypatch.setattr(
        "agent.skill_commands.get_skill_commands",
        lambda: commands,
    )
    monkeypatch.setattr(
        "agent.skill_utils.get_disabled_skill_names",
        lambda platform=None: set(),
    )


def _capture_handle_message_with_agent(runner, captured: dict):
    """Wire _handle_message_with_agent to record the event it receives."""
    async def _capture(event, source, key):
        captured["text"] = event.text
        captured["key"] = key
        return "processed"
    runner._handle_message_with_agent = _capture


@pytest.mark.asyncio
async def test_bundle_command_resolves_and_sends_invocation_message(monkeypatch):
    """A /<bundle> command resolves through resolve_bundle_command_key and
    the built bundle message is forwarded to the agent (not the skill path)."""
    runner = _make_runner()
    captured = {}
    _capture_handle_message_with_agent(runner, captured)

    bundle_kwargs = {}

    def _fake_bundle_build(cmd_key, user_instruction="", task_id=None, platform=None):
        bundle_kwargs.update(
            cmd_key=cmd_key,
            user_instruction=user_instruction,
            task_id=task_id,
            platform=platform,
        )
        return ("BUNDLE-MSG", ["skill-a", "skill-b"], [])

    monkeypatch.setattr(
        "agent.skill_bundles.resolve_bundle_command_key",
        lambda command: "/backend-dev" if command == "backend-dev" else None,
    )
    monkeypatch.setattr(
        "agent.skill_bundles.build_bundle_invocation_message",
        _fake_bundle_build,
    )
    # The skill path must not run when a bundle matches.
    monkeypatch.setattr(
        "agent.skill_commands.resolve_skill_command_key",
        lambda command: (_ for _ in ()).throw(
            AssertionError("skill resolver ran for a bundle command")
        ),
    )
    monkeypatch.setattr(
        "agent.skill_commands.build_skill_invocation_message",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("skill invocation builder ran for a bundle command")
        ),
    )

    result = await runner._handle_message(_make_event("/backend-dev do the thing"))

    assert result == "processed"
    assert captured["text"] == "BUNDLE-MSG"
    assert captured["key"] == build_session_key(_make_source())
    assert bundle_kwargs == {
        "cmd_key": "/backend-dev",
        "user_instruction": "do the thing",
        "task_id": build_session_key(_make_source()),
        "platform": "telegram",
    }


@pytest.mark.asyncio
async def test_bundle_shadows_skill_with_same_name(monkeypatch):
    """When a bundle and a skill share a slug, the bundle wins: the bundle
    message is sent and the skill invocation builder is never called."""
    runner = _make_runner()
    captured = {}
    _capture_handle_message_with_agent(runner, captured)
    _monkeypatch_skill_path(
        monkeypatch, {"/demo": {"name": "demo-skill", "description": "demo"}}
    )

    monkeypatch.setattr(
        "agent.skill_bundles.resolve_bundle_command_key",
        lambda command: "/demo",
    )
    monkeypatch.setattr(
        "agent.skill_bundles.build_bundle_invocation_message",
        lambda *a, **kw: ("BUNDLE-WINS", ["demo-skill"], []),
    )
    # The skill would resolve to the same slug — but must be skipped.
    monkeypatch.setattr(
        "agent.skill_commands.resolve_skill_command_key",
        lambda command: "/demo",
    )
    monkeypatch.setattr(
        "agent.skill_commands.build_skill_invocation_message",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("skill invocation builder ran despite bundle match")
        ),
    )

    result = await runner._handle_message(_make_event("/demo"))

    assert result == "processed"
    assert captured["text"] == "BUNDLE-WINS"


@pytest.mark.asyncio
async def test_non_bundle_command_falls_through_to_skill_path(monkeypatch):
    """A command that is not a bundle resolves via the skill path unchanged."""
    runner = _make_runner()
    captured = {}
    _capture_handle_message_with_agent(runner, captured)
    _monkeypatch_skill_path(
        monkeypatch, {"/gif-search": {"name": "gif-search", "description": "GIFs"}}
    )

    skill_kwargs = {}

    def _fake_skill_build(cmd_key, user_instruction="", task_id=None, runtime_note=""):
        skill_kwargs.update(
            cmd_key=cmd_key,
            user_instruction=user_instruction,
            task_id=task_id,
        )
        return "SKILL-MSG"

    # The bundle resolver is consulted first but returns no match.
    monkeypatch.setattr(
        "agent.skill_bundles.resolve_bundle_command_key",
        lambda command: None,
    )
    monkeypatch.setattr(
        "agent.skill_bundles.build_bundle_invocation_message",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("bundle builder ran for a non-bundle command")
        ),
    )
    monkeypatch.setattr(
        "agent.skill_commands.resolve_skill_command_key",
        lambda command: "/gif-search",
    )
    monkeypatch.setattr(
        "agent.skill_commands.build_skill_invocation_message",
        _fake_skill_build,
    )

    result = await runner._handle_message(_make_event("/gif-search cats"))

    assert result == "processed"
    assert captured["text"] == "SKILL-MSG"
    assert skill_kwargs == {
        "cmd_key": "/gif-search",
        "user_instruction": "cats",
        "task_id": build_session_key(_make_source()),
    }


@pytest.mark.asyncio
async def test_bundle_with_no_loadable_members_returns_guidance(monkeypatch):
    """If build_bundle_invocation_message() returns None (all members missing
    or disabled), the gateway surfaces a clear message instead of silently
    forwarding the raw command to the agent."""
    runner = _make_runner()

    monkeypatch.setattr(
        "agent.skill_bundles.resolve_bundle_command_key",
        lambda command: "/empty-bundle",
    )
    monkeypatch.setattr(
        "agent.skill_bundles.build_bundle_invocation_message",
        lambda *a, **kw: None,
    )

    result = await runner._handle_message(_make_event("/empty-bundle"))

    assert result is not None
    assert "/empty-bundle" in result
    assert "no loadable skills" in result
