"""Tests for the library data layer hardening (Tabulator refactor / 0.2).

Covers two changes made when the frontend moved to Tabulator:
  * `beet list` output is split on the ASCII Unit Separator, not '@@', and each
    item carries beets' stable `id`.
  * edit/remove/delete target `id:<id>` when the client supplies one, and refuse
    to run when no track identifier is present (an empty beets query would match
    the whole library).
"""
import subprocess

import pytest

import beetiful
from beetiful import app, LIST_SEP, LIBRARY_FIELDS


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(beetiful, 'beets_config_dir', str(tmp_path))
    return tmp_path


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def library(config_dir):
    """Create the library.db file so the no-library guard lets endpoints run."""
    (config_dir / 'library.db').write_text('')
    return config_dir


# --- parse_library_item ---------------------------------------------------

def test_parse_includes_id_first():
    line = LIST_SEP.join(['42', 'T', 'A', 'Alb', 'Rock', '2020', '120', 'C', 'note'])
    item = beetiful.parse_library_item(line)
    assert item['id'] == '42'
    assert list(item.keys()) == list(LIBRARY_FIELDS)
    assert item['title'] == 'T' and item['comments'] == 'note'


def test_parse_preserves_values_containing_old_delimiter():
    """A value containing '@@' must no longer corrupt adjacent columns."""
    line = LIST_SEP.join(['7', 'Track @@ Two', 'Artist', 'Album', '', '', '', '', ''])
    item = beetiful.parse_library_item(line)
    assert item['title'] == 'Track @@ Two'
    assert item['artist'] == 'Artist'


def test_parse_includes_path():
    """The filesystem path ($path) is surfaced as the `path` field (issue #16)."""
    assert 'path' in LIBRARY_FIELDS
    values = ['3', 'T', 'A', 'Alb', 'Rock', '2020', '120', 'C', '', '/music/A/Alb/T.mp3']
    item = beetiful.parse_library_item(LIST_SEP.join(values))
    assert item['path'] == '/music/A/Alb/T.mp3'


def test_parse_short_line_defaults_missing_fields():
    item = beetiful.parse_library_item(LIST_SEP.join(['9', 'OnlyTitle']))
    assert item['id'] == '9' and item['title'] == 'OnlyTitle'
    assert item['album'] == '' and item['comments'] == ''


# --- id-based writes ------------------------------------------------------

def _capture_run_beet(monkeypatch):
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

    monkeypatch.setattr(beetiful, 'run_beet', fake)
    return calls


def test_update_targets_id(library, client, monkeypatch):
    calls = _capture_run_beet(monkeypatch)
    resp = client.post('/api/library/update', json={
        'id': '15', 'updatedTrack': {'genre': 'Jazz', 'year': ''}})
    assert resp.status_code == 200
    assert calls == [['beet', 'modify', '-y', 'id:15', 'genre=Jazz']]


@pytest.mark.parametrize('path', ['/api/library/remove', '/api/library/delete'])
def test_remove_delete_target_id(library, client, monkeypatch, path):
    calls = _capture_run_beet(monkeypatch)
    resp = client.post(path, json={'id': '15'})
    assert resp.status_code == 200
    assert calls == [['beet', 'remove', '-f', 'id:15']]


def test_falls_back_to_triple_without_id(library, client, monkeypatch):
    calls = _capture_run_beet(monkeypatch)
    resp = client.post('/api/library/remove', json={
        'title': 't', 'artist': 'a', 'album': 'b'})
    assert resp.status_code == 200
    assert calls == [['beet', 'remove', '-f', 'title:t', 'artist:a', 'album:b']]


@pytest.mark.parametrize('path', [
    '/api/library/update', '/api/library/remove', '/api/library/delete'])
def test_no_identifier_is_rejected_without_running_beets(library, client, monkeypatch, path):
    """No id and an incomplete triple must 400 — never run an empty query that
    would match (and modify/remove) every track."""
    def boom(*a, **k):
        raise AssertionError('beets ran with no track identifier')
    monkeypatch.setattr(beetiful, 'run_beet', boom)

    resp = client.post(path, json={'title': 't'})  # missing artist/album, no id
    assert resp.status_code == 400
