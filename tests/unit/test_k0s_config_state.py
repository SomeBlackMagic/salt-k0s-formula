import importlib.util


MODULE_PATH = 'k0s/_states/k0s_config.py'


def _load_state_module():
    spec = importlib.util.spec_from_file_location('k0s_config', MODULE_PATH)
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
    config = tmp_path / 'k0s.yaml'
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.created(str(config), binary=str(binary))

    assert result['result'] is None
    assert result['changes']['config']['new'] == str(config)
    assert calls == []
    assert not config.exists()


def test_created_fails_when_path_is_a_directory(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    config_dir = tmp_path / 'k0s.yaml'
    config_dir.mkdir()
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.created(str(config_dir), binary=str(binary))

    assert result['result'] is False
    assert 'not a regular file' in result['comment']
    assert calls == []


def test_created_is_idempotent_when_config_exists(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    config = tmp_path / 'k0s.yaml'
    config.write_text('apiVersion: k0s.k0sproject.io/v1beta1\n')
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.created(str(config), binary=str(binary))

    assert result['result'] is True
    assert result['changes'] == {}
    assert calls == []


def test_created_writes_generated_config(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    config = tmp_path / 'k0s.yaml'
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        return {
            'retcode': 0,
            'stdout': 'apiVersion: k0s.k0sproject.io/v1beta1\n',
            'stderr': '',
        }

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.created(str(config), binary=str(binary))

    assert result['result'] is True
    assert result['changes']['config']['old'] == 'missing'
    assert config.read_text() == 'apiVersion: k0s.k0sproject.io/v1beta1\n'
    assert calls == [([str(binary), 'config', 'create'], False)]


def test_created_handles_none_stdout_without_error(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    config = tmp_path / 'k0s.yaml'
    state.__salt__ = {
        'cmd.run_all': lambda command, python_shell: {
            'retcode': 0,
            'stdout': None,
            'stderr': '',
        }
    }

    result = state.created(str(config), binary=str(binary))

    assert result['result'] is True
    assert config.read_text() == ''


def test_created_fails_clearly_when_command_fails(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    config = tmp_path / 'k0s.yaml'
    state.__salt__ = {
        'cmd.run_all': lambda command, python_shell: {
            'retcode': 1,
            'stdout': '',
            'stderr': 'boom',
        }
    }

    result = state.created(str(config), binary=str(binary))

    assert result['result'] is False
    assert 'k0s config create failed' in result['comment']
    assert not config.exists()
