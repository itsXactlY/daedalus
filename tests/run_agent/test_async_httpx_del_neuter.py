"""Tests for the AsyncHttpxClientWrapper.__del__ neuter fix.

The OpenAI SDK's ``AsyncHttpxClientWrapper.__del__`` schedules
``aclose()`` via ``asyncio.get_running_loop().create_task()``.  When GC
fires during CLI idle time, prompt_toolkit's event loop picks up the task
and crashes with "Event loop is closed" because the underlying TCP
transport is bound to a dead worker loop.

The three-layer defence:
1. ``neuter_async_httpx_del()`` replaces ``__del__`` with a no-op.
2. A custom asyncio exception handler silences residual errors.
3. ``cleanup_stale_async_clients()`` evicts stale cache entries.
"""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest



class TestNeuterAsyncHttpxDel:
    """Verify neuter_async_httpx_del replaces __del__ on the SDK class."""

    def test_del_becomes_noop(self):
        """After neuter, __del__ should do nothing (no RuntimeError)."""
        from agent.auxiliary_client import neuter_async_httpx_del

        try:
            from openai._base_client import AsyncHttpxClientWrapper
        except ImportError:
            pytest.skip("openai SDK not installed")

        original_del = AsyncHttpxClientWrapper.__del__
        try:
            neuter_async_httpx_del()
            assert AsyncHttpxClientWrapper.__del__ is not original_del
            wrapper = MagicMock(spec=AsyncHttpxClientWrapper)
            AsyncHttpxClientWrapper.__del__(wrapper)
        finally:
            AsyncHttpxClientWrapper.__del__ = original_del

    def test_neuter_idempotent(self):
        """Calling neuter twice doesn't break anything."""
        from agent.auxiliary_client import neuter_async_httpx_del

        try:
            from openai._base_client import AsyncHttpxClientWrapper
        except ImportError:
            pytest.skip("openai SDK not installed")

        original_del = AsyncHttpxClientWrapper.__del__
        try:
            neuter_async_httpx_del()
            first_del = AsyncHttpxClientWrapper.__del__
            neuter_async_httpx_del()
            second_del = AsyncHttpxClientWrapper.__del__
            assert first_del is not original_del
            assert second_del is not original_del
        finally:
            AsyncHttpxClientWrapper.__del__ = original_del

    def test_neuter_graceful_without_sdk(self):
        """neuter_async_httpx_del doesn't raise if the openai SDK isn't installed."""
        from agent.auxiliary_client import neuter_async_httpx_del

        with patch.dict("sys.modules", {"openai._base_client": None}):
            neuter_async_httpx_del()



class TestCleanupStaleAsyncClients:
    """Verify stale cache entries are evicted and force-closed."""

    def test_removes_stale_entries(self):
        """Entries with a closed loop should be evicted."""
        from agent.auxiliary_client import (
            _client_cache,
            _client_cache_lock,
            cleanup_stale_async_clients,
        )

        loop = asyncio.new_event_loop()
        loop.close()

        mock_client = MagicMock()
        mock_client._client = MagicMock()
        mock_client._client.is_closed = False

        key = ("test_stale", True, "", "", id(loop))
        with _client_cache_lock:
            _client_cache[key] = (mock_client, "test-model", loop)

        try:
            cleanup_stale_async_clients()
            with _client_cache_lock:
                assert key not in _client_cache, "Stale entry should be removed"
        finally:
            with _client_cache_lock:
                _client_cache.pop(key, None)

    def test_keeps_live_entries(self):
        """Entries with an open loop should be preserved."""
        from agent.auxiliary_client import (
            _client_cache,
            _client_cache_lock,
            cleanup_stale_async_clients,
        )

        loop = asyncio.new_event_loop()

        mock_client = MagicMock()
        key = ("test_live", True, "", "", id(loop))
        with _client_cache_lock:
            _client_cache[key] = (mock_client, "test-model", loop)

        try:
            cleanup_stale_async_clients()
            with _client_cache_lock:
                assert key in _client_cache, "Live entry should be preserved"
        finally:
            loop.close()
            with _client_cache_lock:
                _client_cache.pop(key, None)

    def test_keeps_entries_without_loop(self):
        """Sync entries (cached_loop=None) should be preserved."""
        from agent.auxiliary_client import (
            _client_cache,
            _client_cache_lock,
            cleanup_stale_async_clients,
        )

        mock_client = MagicMock()
        key = ("test_sync", False, "", "", 0)
        with _client_cache_lock:
            _client_cache[key] = (mock_client, "test-model", None)

        try:
            cleanup_stale_async_clients()
            with _client_cache_lock:
                assert key in _client_cache, "Sync entry should be preserved"
        finally:
            with _client_cache_lock:
                _client_cache.pop(key, None)
