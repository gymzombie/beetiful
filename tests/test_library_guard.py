"""Tests for the 'no library' guard.

Beetiful must never invoke beets when no library database exists, because
beets would silently create an empty one. Instead every beets-backed endpoint
returns a structured no_library response.
"""
import subprocess

import pytest

import beetiful
from beetiful import app


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(beetiful, 'beets_config_dir', str(tmp_path))
    return tmp_path


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def no_beet(monkeypatch):
    """Fail loudly if any endpoint actually shells out to beets."""
    def boom(*args, **kwargs):
        raise AssertionError('run_beet was called but no library exists')
    monkeypatch.setattr(beetiful, 'run_beet', boom)


# --- resolve_library_path -------------------------------------------------

def test_library_path_defaults_to_beetsdir(config_dir):
    assert beetiful.resolve_library_path() == str(config_dir / 'library.db')


def test_library_path_from_config_absolute(config_dir):
    (config_dir / 'config.yaml').write_text('library: /data/beets/my.db\n')
    assert beetiful.resolve_library_path() == '/data/beets/my.db'


def test_library_path_from_config_relative_to_beetsdir(config_dir):
    (config_dir / 'config.yaml').write_text('library: sub/my.db\n')
    assert beetiful.resolve_library_path() == str(config_dir / 'sub' / 'my.db')


# --- the guard blocks beets when the library is missing -------------------

@pytest.mark.parametrize('method,path', [
    ('get', '/api/stats'),
    ('get', '/api/library'),
])
def test_get_endpoints_blocked_without_library(config_dir, client, no_beet, method, path):
    resp = getattr(client, method)(path)
    assert resp.status_code == 409
    body = resp.get_json()
    assert body['no_library'] is True
    assert body['library_path'] == str(config_dir / 'library.db')
    assert 'beets.readthedocs.io' in body['docs_url']


def test_run_command_blocked_without_library(config_dir, client, no_beet):
    resp = client.post('/api/run-command', json={'command': 'list'})
    assert resp.status_code == 409
    assert resp.get_json()['no_library'] is True


def test_mutating_endpoints_blocked_without_library(config_dir, client, no_beet):
    for path in ('/api/library/remove', '/api/library/delete', '/api/library/update'):
        resp = client.post(path, json={'title': 't', 'artist': 'a', 'album': 'b'})
        assert resp.status_code == 409, path
        assert resp.get_json()['no_library'] is True


# --- when the library exists, the guard lets beets run --------------------

def test_stats_runs_when_library_exists(config_dir, client, monkeypatch):
    (config_dir / 'library.db').write_text('')  # presence is all the guard checks
    fake = subprocess.CompletedProcess(
        ['beet', 'stats'], 0,
        stdout='Tracks: 5\nArtists: 2\nAlbums: 1\nTotal size: 100 MiB\n', stderr='')
    monkeypatch.setattr(beetiful, 'run_beet', lambda *a, **k: fake)
    resp = client.get('/api/stats')
    assert resp.status_code == 200
    assert resp.get_json()['total_tracks'] == '5'


def test_library_runs_when_library_exists(config_dir, client, monkeypatch):
    (config_dir / 'library.db').write_text('')
    fake = subprocess.CompletedProcess(['beet', 'list'], 0, stdout='', stderr='')
    monkeypatch.setattr(beetiful, 'run_beet', lambda *a, **k: fake)
    resp = client.get('/api/library')
    assert resp.status_code == 200
    assert resp.get_json() == {'items': []}
