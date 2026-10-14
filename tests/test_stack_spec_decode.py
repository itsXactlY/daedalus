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
        assert argv[argv.index("--spec-type") + 1] == "draft-dflash,ngram-mod"
        assert argv[argv.index("--spec-ngram-mod-n-max") + 1] == "31"
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


class TestIdleSlotClearingUnderUnifiedKv:
    """--cache-idle-slots is ON by default (it only needs --cache-ram, which
    defaults to 8192 MiB), and under a unified KV cache llama-server's task
    loop calls slot.prompt_clear() on every idle slot each time a task starts
    -- see [TAG_IDLE_SLOT_CLEAR] in tools/server/server-context.cpp.

    With two slots that means the sidekick's hygiene task wipes main's cached
    prefix and main's next turn wipes the sidekick's, so both slots spend
    their time re-prefilling the same history. It looks exactly like the two
    slots fighting over the same work, and nothing in the log says so.

    Only harmful when the KV cache is unified; without -kvu, clearing a slot
    frees no reusable room and the server only publishes a RAM-cache copy.
    """

    def test_unified_kv_disables_idle_slot_clearing(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_KV_POOL="2048", MAIN_SLOTS="2"),
                                "/models/main.gguf")
        assert "-kvu" in argv
        assert "--no-cache-idle-slots" in argv

    def test_single_slot_does_not_need_it(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_SLOTS="1", MAIN_KV_POOL=""),
                                "/models/main.gguf")
        assert "-kvu" not in argv
        assert "--no-cache-idle-slots" not in argv


class TestLocallyBuiltDraftModel:
    """The drafter that actually won here was built locally into ~/models and
    has no HuggingFace repo. model_path() searched only the HF cache, so such
    a file was unreachable from stack.conf: `start` fell through to whatever
    repo-hosted draft was named instead -- silently, with a healthy server.
    """

    def test_absolute_path_resolves_without_a_repo(self, tmp_path, monkeypatch):
        gguf = tmp_path / "dflash2-Q4_K_M.gguf"
        gguf.write_bytes(b"GGUF")
        assert stack.model_path("", str(gguf)) == str(gguf)

    def test_missing_local_file_is_not_silently_accepted(self, tmp_path):
        assert stack.model_path("", str(tmp_path / "absent.gguf")) == ""

    def test_launch_uses_the_local_draft(self, tmp_path, monkeypatch):
        gguf = tmp_path / "dflash2-Q4_K_M.gguf"
        gguf.write_bytes(b"GGUF")
        argv = stack._main_argv(
            _conf(MAIN_DRAFT_REPO="", MAIN_DRAFT_FILE=str(gguf),
                  MAIN_DRAFT_N_MAX="5", MAIN_DRAFT_N_MIN="0"),
            "/models/main.gguf")
        assert argv[argv.index("--model-draft") + 1] == str(gguf)
        assert argv[argv.index("--spec-type") + 1] == "draft-dflash,ngram-mod"
        assert argv[argv.index("--spec-draft-n-max") + 1] == "5"
        assert argv[argv.index("-ngld") + 1] == "99"

    def test_a_bare_filename_still_means_the_hf_cache(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path(
            {("some/draft-repo", "d.gguf"): "/hf/d.gguf"}))
        argv = stack._main_argv(
            _conf(MAIN_DRAFT_REPO="some/draft-repo", MAIN_DRAFT_FILE="d.gguf"),
            "/models/main.gguf")
        assert argv[argv.index("--model-draft") + 1] == "/hf/d.gguf"


class TestUnifiedMemoryIsSetForMain:
    """Block KV streaming overshooting MAIN_KV_POOL is a startup OOM without
    GGML_CUDA_ENABLE_UNIFIED_MEMORY=1 and a slowdown with it. The hand-written
    launch always set it; the stack inherited a bare environment, so the two
    diverged under exactly the condition that matters."""

    def test_start_one_merges_env_over_the_inherited_one(self, monkeypatch, tmp_path):
        seen = {}

        class _Proc:
            pid = 4242

        def fake_popen(argv, **kwargs):
            seen.update(kwargs)
            return _Proc()

        monkeypatch.setattr(stack.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(stack, "state_of", lambda name: "stopped")
        monkeypatch.setattr(stack, "log_file", lambda name: tmp_path / "x.log")
        monkeypatch.setattr(stack, "pid_file", lambda name: tmp_path / "x.pid")
        assert stack.start_one("main", ["/bin/true"],
                               env={"GGML_CUDA_ENABLE_UNIFIED_MEMORY": "1"})
        env = seen["env"]
        assert env["GGML_CUDA_ENABLE_UNIFIED_MEMORY"] == "1"
        assert "PATH" in env, "must extend the inherited environment, not replace it"

    def test_no_env_leaves_the_process_environment_alone(self, monkeypatch, tmp_path):
        seen = {}

        class _Proc:
            pid = 4243

        monkeypatch.setattr(stack.subprocess, "Popen",
                            lambda argv, **kw: (seen.update(kw), _Proc())[1])
        monkeypatch.setattr(stack, "state_of", lambda name: "stopped")
        monkeypatch.setattr(stack, "log_file", lambda name: tmp_path / "y.log")
        monkeypatch.setattr(stack, "pid_file", lambda name: tmp_path / "y.pid")
        assert stack.start_one("aux", ["/bin/true"])
        assert seen["env"] is None


class TestPromptCacheBudget:
    """llama-server's prompt cache lives in ordinary host RAM and defaults to
    8192 MiB. It is swappable, unlike the block-KV pinned buffer, so on a
    machine that is already tight it does not fail -- it pages, and every
    lookup becomes a disk fault. Throughput then decays over hours rather
    than falling over, which is a much harder symptom to attribute.
    """

    def test_a_budget_is_always_passed(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(), "/models/main.gguf")
        assert "--cache-ram" in argv, "leaving it at llama.cpp's 8192 MiB default is a choice, not an omission"

    def test_default_is_well_under_the_llama_cpp_default(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(), "/models/main.gguf")
        assert int(argv[argv.index("--cache-ram") + 1]) < 8192

    def test_conf_value_is_honored(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_CACHE_RAM="512"), "/models/main.gguf")
        assert argv[argv.index("--cache-ram") + 1] == "512"

    def test_zero_disables_the_cache_rather_than_being_dropped(self, monkeypatch):
        """0 is a meaningful value to llama.cpp (cache off), so it must be
        passed through, not treated as unset."""
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_CACHE_RAM="0"), "/models/main.gguf")
        assert argv[argv.index("--cache-ram") + 1] == "0"


class TestPinnedLaunch:
    """2026-10-14: the doctor launch drifted from the measured -np 3 one.

    --reasoning on put enable_thinking=true in the template kwargs, which beat
    reasoning_effort "none", so titles and reviews thought on slot 0; the dense
    stack also forced unified memory, which spills instead of failing.
    """

    def test_reasoning_is_left_to_the_template_by_default(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_REASONING_BUDGET="-1"), "/models/main.gguf")
        assert "--reasoning" not in argv
        assert "--reasoning-budget" not in argv

    def test_reasoning_and_budget_pass_through_when_set(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_REASONING="on"), "/models/main.gguf")
        assert argv[argv.index("--reasoning") + 1] == "on"
        assert argv[argv.index("--reasoning-budget") + 1] == "12000"

    def test_slot_window_and_measured_knobs(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(MAIN_SLOT_CTX="57344", MAIN_SEED="12071"), "/models/main.gguf")
        assert argv[argv.index("--kv-unified-per-slot") + 1] == "57344"
        assert argv[argv.index("--seed") + 1] == "12071"
        assert argv[argv.index("--load-mode") + 1] == "mlock"
        assert argv[argv.index("-ctxcp") + 1] == "8"
        assert argv[argv.index("--ctx-checkpoints-total") + 1] == "6"
        assert argv[argv.index("--temp") + 1] == "0.4"

    def test_no_slot_window_unless_configured(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", _fake_model_path({}))
        argv = stack._main_argv(_conf(), "/models/main.gguf")
        assert "--kv-unified-per-slot" not in argv
        assert "--seed" not in argv

    def test_dense_unified_memory_is_opt_in(self, monkeypatch):
        monkeypatch.setattr(stack, "model_path", lambda repo, name: "/models/x.gguf")
        _m, _a, env = stack.main_launch(_conf(), "dense")
        assert env == {}
        _m, _a, env = stack.main_launch(_conf(MAIN_CUDA_UNIFIED_MEMORY="1"), "dense")
        assert env == {"GGML_CUDA_ENABLE_UNIFIED_MEMORY": "1"}
        _m, _a, env = stack.main_launch(_conf(), "a3b")
        assert env == {"GGML_CUDA_ENABLE_UNIFIED_MEMORY": "1"}

    def test_command_prints_a_line_the_shell_runs_as_start_would(self, monkeypatch, capsys):
        import argparse
        import shlex
        monkeypatch.setattr(stack, "model_path", lambda repo, name: "/models/x.gguf")
        monkeypatch.setattr(stack, "load_conf", lambda: _conf(MAIN_CUDA_UNIFIED_MEMORY="1"))
        assert stack.cmd_command(argparse.Namespace(model="dense")) == 0
        # the shell drops backslash-newline; shlex keeps it as a word
        words = shlex.split(capsys.readouterr().out.replace("\\\n", ""))
        _m, argv, _e = stack.main_launch(_conf(MAIN_CUDA_UNIFIED_MEMORY="1"), "dense")
        assert words == ["GGML_CUDA_ENABLE_UNIFIED_MEMORY=1"] + argv
