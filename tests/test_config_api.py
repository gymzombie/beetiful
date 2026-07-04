"""Tests for the /api/config read/write endpoints.

Covers the config-editor poisoning bug: a GET that 404s must not have its
error body written back to disk by a subsequent POST, and the .yaml/.yml
filename tolerance.
"""
import os

import pytest

import beetiful
from beetiful import app, CONFIG_FILENAMES


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Point the app's config directory at a temp dir for each test."""
    monkeypatch.setattr(beetiful, 'beets_config_dir', str(tmp_path))
    return tmp_path


@pytest.fixture
def client():
    return app.test_client()


VALID_CONFIG = 'directory: /music\nlibrary: /config/beets/library.db\n'
# The exact error body a missing-config GET returns — the string that poisoned
# the user's config directory in the field report.
POISON = 'Config file not found at /config/beets/config.yaml.'


def test_get_reads_config_yaml(config_dir, client):
    (config_dir / 'config.yaml').write_text(VALID_CONFIG)
    resp = client.get('/api/config')
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == VALID_CONFIG


def test_get_falls_back_to_config_yml(config_dir, client):
    # Only the .yml variant exists — tolerance should find it.
    (config_dir / 'config.yml').write_text(VALID_CONFIG)
    resp = client.get('/api/config')
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == VALID_CONFIG


def test_get_prefers_yaml_over_yml(config_dir, client):
    (config_dir / 'config.yaml').write_text('directory: /yaml\n')
    (config_dir / 'config.yml').write_text('directory: /yml\n')
    resp = client.get('/api/config')
    assert resp.status_code == 200
    assert '/yaml' in resp.get_data(as_text=True)


def test_get_missing_returns_404(config_dir, client):
    resp = client.get('/api/config')
    assert resp.status_code == 404


def test_post_rejects_the_404_error_body(config_dir, client):
    """Regression: the GET error text must not be writable as config."""
    resp = client.post('/api/config', data=POISON.encode('utf-8'))
    assert resp.status_code == 400
    # And nothing was written to disk.
    for name in CONFIG_FILENAMES:
        assert not (config_dir / name).exists()


def test_post_rejects_malformed_yaml(config_dir, client):
    resp = client.post('/api/config', data=b'key: [unclosed')
    assert resp.status_code == 400
    assert not (config_dir / 'config.yaml').exists()


def test_post_rejects_non_mapping(config_dir, client):
    # A bare list is valid YAML but not a valid config.
    resp = client.post('/api/config', data=b'- just\n- a\n- list\n')
    assert resp.status_code == 400
    assert not (config_dir / 'config.yaml').exists()


def test_post_writes_valid_config(config_dir, client):
    resp = client.post('/api/config', data=VALID_CONFIG.encode('utf-8'))
    assert resp.status_code == 200
    assert (config_dir / 'config.yaml').read_text() == VALID_CONFIG


def test_post_writes_back_to_existing_yml(config_dir, client):
    # If the config lives in config.yml, edits should save there, not create
    # a competing config.yaml.
    (config_dir / 'config.yml').write_text('directory: /old\n')
    new = 'directory: /new\n'
    resp = client.post('/api/config', data=new.encode('utf-8'))
    assert resp.status_code == 200
    assert (config_dir / 'config.yml').read_text() == new
    assert not (config_dir / 'config.yaml').exists()
