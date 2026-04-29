import importlib.util


MODULE_PATH = 'k0s/_states/k0s_cluster.py'


def _load_state_module():
    spec = importlib.util.spec_from_file_location('k0s_cluster', MODULE_PATH)
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


def test_operational_is_idempotent_when_cluster_responds(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        return {'retcode': 0, 'stdout': 'node\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.operational('k0s', binary=str(binary))

    assert result['result'] is True
    assert result['changes'] == {}
    assert calls == [([str(binary), 'kubectl', 'get', 'nodes'], False)]


def test_operational_reports_pending_change_in_test_mode(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__opts__ = {'test': True}
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        return {'retcode': 1, 'stdout': '', 'stderr': 'not ready'}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.operational('k0s', binary=str(binary))

    assert result['result'] is None
    assert result['changes']['cluster']['new'] == 'operational'
    assert calls == [([str(binary), 'kubectl', 'get', 'nodes'], False)]


def test_operational_waits_until_cluster_responds(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.time.sleep = lambda interval: None
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        if len(calls) == 1:
            return {'retcode': 1, 'stdout': '', 'stderr': 'not ready'}
        return {'retcode': 0, 'stdout': 'node\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.operational('k0s', binary=str(binary), timeout=10, interval=1)

    assert result['result'] is True
    assert result['changes']['cluster']['old'] == 'not operational'
    assert calls == [
        ([str(binary), 'kubectl', 'get', 'nodes'], False),
        ([str(binary), 'kubectl', 'get', 'nodes'], False),
    ]


def test_operational_fails_after_timeout(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        return {'retcode': 1, 'stdout': '', 'stderr': 'not ready'}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.operational('k0s', binary=str(binary), timeout=0, interval=0)

    assert result['result'] is False
    assert 'not ready' in result['comment']
    assert calls == [([str(binary), 'kubectl', 'get', 'nodes'], False)]
