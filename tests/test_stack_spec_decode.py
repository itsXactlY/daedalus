"""_main_argv's speculative-decoding and vision defaults.

2026-09-12: DFlash2 was fully benchmarked in ~/projects/specbench (GOAT.sh)
but never actually wired into the real launch path -- _main_argv hardcoded
draft-mtp,ngram-mod unconditionally, and separately loaded the ~890MB vision
projector whenever it happened to be present, regardless of whether there was
VRAM headroom for it. Both are config-driven now: DFlash2 when a draft model
resolves, MTP+ngram-mod fallback otherwise; vision only when MAIN_VISION=1.
"""

import daedalus_cli.stack as stack


def _conf(**overrides):
    values = {
        "MAIN_REPO": "some/repo", "MAIN_HOST": "127.0.0.1", "MAIN_PORT": "8080",
        "MAIN_CTX": "81920", "MAIN_NGL": "99", "MAIN_THREADS": "8",
        "MAIN_SLOTS": "2", "MAIN_REASONING_BUDGET": "12000",
    }
    values.update(overrides)
    return stack.StackConf(values)


def _fake_model_path(paths):
    def _fn(repo, filename):
        return paths.get((repo, filename), "")
    return _fn


class TestKvCacheQuant:
    """q4_0/q4_0 was hardcoded -- GOAT.sh (the winning benchmark) uses
    q8_0/q4_0. K-cache is more sensitive to attention accuracy than V, so
    q4_0 on K was a silent quality regression, not a deliberate VRAM trade.
    """

    def test_defaults_match_the_benchmarked_config(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(), "/models/main.gguf")
        assert argv[argv.index("-ctk") + 1] == "q8_0"
        assert argv[argv.index("-ctv") + 1] == "q4_0"

    def test_explicit_conf_values_are_honored(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_CTK="q4_0", MAIN_CTV="q8_0"), "/models/main.gguf")
        assert argv[argv.index("-ctk") + 1] == "q4_0"
        assert argv[argv.index("-ctv") + 1] == "q8_0"


class TestSpeculativeDecoding:
    def test_falls_back_to_mtp_when_no_draft_configured(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(), "/models/main.gguf")
        assert "--model-draft" not in argv
        assert "draft-mtp,ngram-mod" in argv
        assert "draft-dflash" not in argv

    def test_uses_dflash2_when_draft_model_resolves(self, monkeypatch):
        draft = "/cache/Qwen3.8-27B-DFlash2-Q2_K_S-MIX.gguf"
        monkeypatch.setattr(
            stack, "model_path",
            _fake_model_path({("HermiHg/x", "draft.gguf"): draft}),
        )
        conf = _conf(
            MAIN_DRAFT_REPO="HermiHg/x", MAIN_DRAFT_FILE="draft.gguf",
            MAIN_DRAFT_N_MAX="4", MAIN_DRAFT_N_MIN="1",
        )
        argv = stack._main_argv(conf, "/models/main.gguf")
        assert "--model-draft" in argv
        assert argv[argv.index("--model-draft") + 1] == draft
        assert "draft-dflash" in argv
        assert argv[argv.index("--spec-draft-n-max") + 1] == "4"
        assert argv[argv.index("--spec-draft-n-min") + 1] == "1"
        assert "draft-mtp,ngram-mod" not in argv

    def test_falls_back_when_draft_configured_but_file_missing(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        conf = _conf(MAIN_DRAFT_REPO="HermiHg/x", MAIN_DRAFT_FILE="draft.gguf")
        argv = stack._main_argv(conf, "/models/main.gguf")
        assert "--model-draft" not in argv
        assert "draft-mtp,ngram-mod" in argv


class TestMmprojResolution:
    """MMPROJ='an absolute path only' sits right next to MAIN_MMPROJ_FILE
    (a bare filename) -- setting MMPROJ to that same bare filename, the
    obvious thing to try without reading the fine print, silently broke
    vision (observed live 2026-09-12: 'MAIN_VISION=1 but no projector' right
    after `daedalus doctor stack` had reported the projector present)."""

    def test_mmproj_set_to_the_bare_filename_still_resolves(self, monkeypatch):
        resolved = "/cache/models--x/snapshots/y/mmproj-Qwen3.8-27B-BF16.gguf"
        monkeypatch.setattr(
            stack, "model_path",
            _fake_model_path({("some/repo", "mmproj-Qwen3.8-27B-BF16.gguf"): resolved}),
        )
        conf = _conf(MMPROJ="mmproj-Qwen3.8-27B-BF16.gguf")
        assert conf.mmproj == resolved

    def test_a_real_absolute_path_is_used_as_is(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        monkeypatch.setattr(stack.os.path, "isfile", lambda p: p == "/abs/custom.gguf")
        conf = _conf(MMPROJ="/abs/custom.gguf")
        assert conf.mmproj == "/abs/custom.gguf"

    def test_a_broken_bare_filename_reports_itself_not_silently_empty(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        conf = _conf(MMPROJ="typo-name.gguf")
        assert conf.mmproj == "typo-name.gguf"

    def test_empty_mmproj_still_falls_back_to_main_mmproj_file(self, monkeypatch):
        resolved = "/cache/mmproj.gguf"
        monkeypatch.setattr(
            stack, "model_path",
            _fake_model_path({("some/repo", "mmproj-Qwen3.8-27B-BF16.gguf"): resolved}),
        )
        conf = _conf(MMPROJ="", MAIN_MMPROJ_FILE="mmproj-Qwen3.8-27B-BF16.gguf")
        assert conf.mmproj == resolved


class TestVisionOptIn:
    def test_no_mmproj_flags_when_vision_off_even_if_projector_present(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        monkeypatch.setattr(stack.os.path, "isfile", lambda p: True)
        monkeypatch.setattr(stack.StackConf, "mmproj", property(lambda self: "/cache/mmproj.gguf"))
        argv = stack._main_argv(_conf(MAIN_VISION="0"), "/models/main.gguf")
        assert "-mm" not in argv

    def test_mmproj_flags_present_when_vision_on(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        monkeypatch.setattr(stack.os.path, "isfile", lambda p: True)
        monkeypatch.setattr(stack.StackConf, "mmproj", property(lambda self: "/cache/mmproj.gguf"))
        argv = stack._main_argv(_conf(MAIN_VISION="1"), "/models/main.gguf")
        assert "-mm" in argv
        assert argv[argv.index("-mm") + 1] == "/cache/mmproj.gguf"

    def test_vision_off_by_default(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        monkeypatch.setattr(stack.os.path, "isfile", lambda p: True)
        monkeypatch.setattr(stack.StackConf, "mmproj", property(lambda self: "/cache/mmproj.gguf"))
        argv = stack._main_argv(_conf(), "/models/main.gguf")
        assert "-mm" not in argv
