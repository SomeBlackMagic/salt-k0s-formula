import importlib.util
import os
import time


MODULE_PATH = 'k0s/_states/k0s_token.py'


def _load_state_module():
    spec = importlib.util.spec_from_file_location('k0s_token', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__opts__ = {'test': False}
    module.__salt__ = {}
    return module


def _create_binary(tmp_path):
    binary = tmp_path / 'k0s'
    binary.write_text('#!/bin/sh\n')
    binary.chmod(0o755)
    return binary


def test_created_reports_pending_change_in_test_mode(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    token = tmp_path / 'worker-token'
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.created(str(token), ttl=24, binary=str(binary))

    assert result['result'] is None
    assert result['changes']['token']['old'] == 'missing'
    assert calls == []
    assert not token.exists()


def test_created_is_idempotent_when_token_is_current(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    token = tmp_path / 'worker-token'
    token.write_text('join-token\n')
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.created(str(token), ttl=24, binary=str(binary))

    assert result['result'] is True
    assert result['changes'] == {}
    assert calls == []


def test_created_treats_ttl_zero_as_non_expiring(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    token = tmp_path / 'worker-token'
    token.write_text('join-token\n')
    old_time = time.time() - 365 * 24 * 60 * 60
    os.utime(token, (old_time, old_time))
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.created(str(token), ttl=0, binary=str(binary))

    assert result['result'] is True
    assert result['changes'] == {}
    assert calls == []


def test_created_replaces_expired_token(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    token = tmp_path / 'worker-token'
    token.write_text('old-token\n')
    old_time = time.time() - 2 * 60 * 60
    os.utime(token, (old_time, old_time))
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        return {'retcode': 0, 'stdout': 'new-token\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.created(str(token), ttl=1, binary=str(binary))

    assert result['result'] is True
    assert result['changes']['token']['old'] == 'expired'
    assert token.read_text() == 'new-token\n'
    assert calls == [([str(binary), 'token', 'create', '--role', 'worker'], False)]


def test_created_fails_when_command_returns_empty_token(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    token = tmp_path / 'worker-token'
    state.__salt__ = {
        'cmd.run_all': lambda command, python_shell: {
            'retcode': 0,
            'stdout': '\n',
            'stderr': '',
        }
    }

    result = state.created(str(token), binary=str(binary))

    assert result['result'] is False
    assert 'empty token' in result['comment']
    assert not token.exists()
