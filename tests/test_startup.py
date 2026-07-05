"""Regression guard for the #11 + #15 merge collision.

check_config_file() referenced a module-level `config_path` that #15 removed,
so `import beetiful` (which calls it at import time) crashed with NameError.
These tests exercise the startup path directly.
"""
import beetiful


def test_app_imported():
    assert beetiful.app is not None


def test_check_config_file_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(beetiful, 'beets_config_dir', str(tmp_path))
    beetiful.check_config_file()                       # no config present -> warns
    (tmp_path / 'config.yaml').write_text('directory: /music\n')
    beetiful.check_config_file()                       # config present -> info
    (tmp_path / 'config.yaml').unlink()
    (tmp_path / 'config.yml').write_text('directory: /music\n')
    beetiful.check_config_file()                       # .yml tolerated too
