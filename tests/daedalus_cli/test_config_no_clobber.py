"""save_config patches the operator's file; it never rewrites it wholesale.

Every caller does ``load_config()`` -> change -> ``save_config()``, and
``load_config()`` is the file deep-merged with all defaults and with ``${VAR}``
expanded. Dumping that back froze every default into config.yaml, wrote
secrets in place of env references, and turned one-key changes into a rewrite
of the whole file on every update and model switch. These run against real
files in the test's DAEDALUS_HOME.
"""

import os

import yaml

from daedalus_cli import config as C


OPERATOR_FILE = """\
_config_version: 16
model:
  provider: custom
  base_url: http://127.0.0.1:8080/v1
providers:
  openrouter:
    api_key: ${NOCLOBBER_TEST_KEY}
auxiliary:
  compression:
    provider: custom
    base_url: http://127.0.0.1:8080/v1
    timeout: 120
display:
  compact: true
tts:
  provider: edge
  mistral:
    model: voxtral-mini-tts-2603
"""


def _write(text=OPERATOR_FILE):
    path = C.get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _raw():
    return yaml.safe_load(C.get_config_path().read_text(encoding="utf-8"))


def _backups():
    d = C.get_daedalus_home() / "backups" / "config.yaml"
    return sorted(d.iterdir()) if d.is_dir() else []


def test_a_one_key_change_writes_only_that_key():
    _write()
    before = _raw()

    cfg = C.load_config()
    cfg["display"]["compact"] = False
    C.save_config(cfg)

    after = _raw()
    assert after["display"] == {"compact": False}
    # Nothing from DEFAULT_CONFIG is materialised into the file.
    assert set(after) == set(before)
    assert after["auxiliary"] == before["auxiliary"]
    assert "summary_provider" not in (after.get("compression") or {})


def test_env_references_are_never_written_out_as_secrets(monkeypatch):
    monkeypatch.setenv("NOCLOBBER_TEST_KEY", "sk-must-not-land-on-disk")
    _write()

    cfg = C.load_config()
    assert cfg["providers"]["openrouter"]["api_key"] == "sk-must-not-land-on-disk"
    cfg["display"]["compact"] = False
    C.save_config(cfg)

    text = C.get_config_path().read_text(encoding="utf-8")
    assert "${NOCLOBBER_TEST_KEY}" in text
    assert "sk-must-not-land-on-disk" not in text


def test_a_removed_key_is_removed():
    _write()
    cfg = C.load_config()
    del cfg["tts"]["mistral"]
    C.save_config(cfg)
    assert "mistral" not in _raw()["tts"]


def test_saving_what_is_already_there_touches_nothing():
    path = _write()
    mtime = path.stat().st_mtime_ns

    C.save_config(C.load_config())

    assert path.stat().st_mtime_ns == mtime
    assert _backups() == []


def test_every_real_write_is_backed_up_first_and_rotated(monkeypatch):
    monkeypatch.setattr(C, "CONFIG_BACKUP_KEEP", 3)
    _write()
    for i in range(5):
        cfg = C.load_config()
        cfg["display"]["compact"] = bool(i % 2)
        C.save_config(cfg)

    backups = _backups()
    assert len(backups) == 3
    assert all(oct(b.stat().st_mode & 0o777) == "0o600" for b in backups)
    # The oldest surviving backup is a real prior state of the file.
    assert yaml.safe_load(backups[0].read_text())["model"]["provider"] == "custom"


def test_update_migration_leaves_the_operators_routing_alone():
    _write()
    before = _raw()

    C.migrate_config(interactive=False, quiet=True)

    after = _raw()
    assert after["auxiliary"] == before["auxiliary"]
    assert after["model"] == before["model"]
    assert after["providers"] == before["providers"]


def test_a_missing_file_is_still_created_in_full():
    path = C.get_config_path()
    if path.exists():
        path.unlink()
    C.save_config({"model": {"provider": "custom"}, "display": {"compact": True}})
    assert _raw()["model"]["provider"] == "custom"


def test_env_writes_are_backed_up_too():
    env = C.get_env_path()
    env.parent.mkdir(parents=True, exist_ok=True)
    env.write_text("KEEP_ME=1\n", encoding="utf-8")

    C.save_env_value("NOCLOBBER_OTHER", "2")

    d = C.get_daedalus_home() / "backups" / "env"
    assert d.is_dir()
    assert any(p.read_text() == "KEEP_ME=1\n" for p in d.iterdir())
    os.environ.pop("NOCLOBBER_OTHER", None)
