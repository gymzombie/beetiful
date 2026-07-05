"""Tests for env_flag, which gates Flask debug mode (#1).

Debug must be OFF unless FLASK_DEBUG is explicitly truthy, since the Werkzeug
debugger is an RCE vector on an exposed instance.
"""
import pytest

from beetiful import env_flag


@pytest.mark.parametrize('value', ['1', 'true', 'True', 'TRUE', 'yes', 'on', ' on '])
def test_truthy_values_enable(monkeypatch, value):
    monkeypatch.setenv('FLASK_DEBUG', value)
    assert env_flag('FLASK_DEBUG') is True


@pytest.mark.parametrize('value', ['0', 'false', 'no', 'off', '', 'garbage', 'debug'])
def test_non_truthy_values_disable(monkeypatch, value):
    monkeypatch.setenv('FLASK_DEBUG', value)
    assert env_flag('FLASK_DEBUG') is False


def test_unset_defaults_to_false(monkeypatch):
    monkeypatch.delenv('FLASK_DEBUG', raising=False)
    assert env_flag('FLASK_DEBUG') is False


def test_unset_honors_explicit_default(monkeypatch):
    monkeypatch.delenv('SOME_FLAG', raising=False)
    assert env_flag('SOME_FLAG', default=True) is True
