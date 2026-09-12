"""Every bundled memory provider must actually construct.

_load_provider_from_dir finds the class, calls it, and swallows any
exception with `except Exception: pass` -- so a provider that cannot be
instantiated degrades to the single line

    Memory provider 'mazemaker' loaded but no provider instance found

and the agent runs with no memory at all: no mazemaker_* tools in the tool
list, no sync_turn, no soak_reasoning, no prefetch fallback.

It happened: a module-level helper was inserted into the middle of the
class body. At column 0 it ended the class, and everything after it --
get_tool_schemas, handle_tool_call, sync_turn -- became unreachable code
nested inside that helper, after its return. Syntactically valid, so the
module imported cleanly and every test that imported a module-level symbol
from it stayed green while the provider was gone.

Importing a name proves the module parses. It does not prove the class
survived.
"""

import pytest

from plugins.memory import find_provider_dir, list_memory_provider_names


def _bundled_names():
    return list_memory_provider_names()


class TestBundledProvidersConstruct:
    def test_there_are_bundled_providers_to_check(self):
        assert _bundled_names(), "no providers discovered at all"

    @pytest.mark.parametrize("name", _bundled_names())
    def test_provider_instantiates(self, name):
        from plugins.memory import _load_provider_from_dir
        d = find_provider_dir(name)
        assert d is not None, f"{name} not found on disk"
        provider = _load_provider_from_dir(d)
        assert provider is not None, (
            f"{name} loaded but produced no instance — most likely an "
            f"unimplemented abstract method, silently swallowed"
        )

    @pytest.mark.parametrize("name", _bundled_names())
    def test_provider_satisfies_the_abstract_surface(self, name):
        """The failure mode is an abstract method going missing, so check the
        contract rather than a hand-picked list of method names."""
        from agent.memory_provider import MemoryProvider
        from plugins.memory import _load_provider_from_dir
        provider = _load_provider_from_dir(find_provider_dir(name))
        assert isinstance(provider, MemoryProvider)
        missing = [m for m in getattr(MemoryProvider, "__abstractmethods__", ())
                   if not hasattr(provider, m)]
        assert not missing, f"{name} is missing {missing}"


class TestMazemakerSurface:
    """The provider the harness actually runs on."""

    def _provider(self):
        from plugins.memory import _load_provider_from_dir
        p = _load_provider_from_dir(find_provider_dir("mazemaker"))
        assert p is not None, "mazemaker provider did not instantiate"
        return p

    def test_it_exposes_tools(self):
        schemas = self._provider().get_tool_schemas()
        assert schemas, "no mazemaker tools would reach the model"

    @pytest.mark.parametrize("method", [
        "sync_turn", "soak_reasoning", "prefetch",
        "history_pointer", "handle_tool_call",
    ])
    def test_the_methods_the_harness_calls_are_present(self, method):
        assert callable(getattr(self._provider(), method, None))
