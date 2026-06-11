import importlib.util


MODULE_PATH = 'k0s/_states/k0s_controller.py'


def _load_state_module():
    spec = importlib.util.spec_from_file_location('k0s_controller', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__opts__ = {'test': False}
    module.__salt__ = {}
    module._systemd_available = lambda: True
    return module


def _create_prerequisites(tmp_path):
    binary = tmp_path / 'k0s'
    config = tmp_path / 'k0s.yaml'

    binary.write_text('#!/bin/sh\n')
    binary.chmod(0o755)
    config.write_text('apiVersion: k0s.k0sproject.io/v1beta1\n')
    return binary, config


def _write_unit(unit_path, binary, config, data_dir, extra_args=''):
    unit_path.write_text(
        '[Service]\n'
        'ExecStart={0} controller --config={1} --data-dir={2}{3}\n'.format(
            binary,
            config,
            data_dir,
            extra_args,
        )
    )


def test_installed_reports_pending_change_in_test_mode(tmp_path):
    state = _load_state_module()
    binary, config = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0scontroller.service'
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.installed(
        'k0scontroller',
        config=str(config),
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
    )

    assert result['result'] is None
    assert result['changes']['unit']['old'] == 'missing'
    assert result['changes']['unit']['new'] == 'installed'
    assert calls == []


def test_installed_fails_clearly_when_binary_is_missing(tmp_path):
    state = _load_state_module()
    config = tmp_path / 'k0s.yaml'
    config.write_text('apiVersion: k0s.k0sproject.io/v1beta1\n')

    result = state.installed(
        'k0scontroller',
        config=str(config),
        data_dir='/var/lib/k0s',
        binary=str(tmp_path / 'missing-k0s'),
        unit_path=str(tmp_path / 'k0scontroller.service'),
    )

    assert result['result'] is False
    assert 'Missing required file(s)' in result['comment']
    assert 'missing-k0s' in result['comment']


def test_installed_creates_unit_with_requested_arguments(tmp_path):
    state = _load_state_module()
    binary, config = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0scontroller.service'
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        _write_unit(
            unit_path,
            binary,
            config,
            '/var/lib/k0s',
            ' --enable-worker=true --no-taints=true --debug',
        )
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.installed(
        'k0scontroller',
        config=str(config),
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
        enable_worker=True,
        no_taints=True,
        extra_args='--debug',
    )

    assert result['result'] is True
    assert result['changes']['unit']['old'] == 'missing'
    assert calls == [
        (
            [
                str(binary),
                'install',
                'controller',
                '--config',
                str(config),
                '--data-dir',
                '/var/lib/k0s',
                '--enable-worker',
                '--no-taints',
                '--debug',
            ],
            False,
        )
    ]


def test_installed_creates_single_node_unit(tmp_path):
    state = _load_state_module()
    binary, config = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0scontroller.service'
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        _write_unit(
            unit_path,
            binary,
            config,
            '/var/lib/k0s',
            ' --single=true',
        )
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.installed(
        'k0scontroller',
        config=str(config),
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
        single=True,
    )

    assert result['result'] is True
    assert calls == [
        (
            [
                str(binary),
                'install',
                'controller',
                '--config',
                str(config),
                '--data-dir',
                '/var/lib/k0s',
                '--single',
            ],
            False,
        )
    ]


def test_installed_is_idempotent_when_unit_matches(tmp_path):
    state = _load_state_module()
    binary, config = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0scontroller.service'
    _write_unit(unit_path, binary, config, '/var/lib/k0s')
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.installed(
        'k0scontroller',
        config=str(config),
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
    )

    assert result['result'] is True
    assert result['changes'] == {}
    assert calls == []


def test_installed_uses_force_when_existing_unit_arguments_change(tmp_path):
    state = _load_state_module()
    binary, config = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0scontroller.service'
    _write_unit(unit_path, binary, config, '/var/lib/k0s')
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        _write_unit(
            unit_path,
            binary,
            config,
            '/var/lib/k0s',
            ' --enable-worker=true',
        )
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.installed(
        'k0scontroller',
        config=str(config),
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
        enable_worker=True,
    )

    assert result['result'] is True
    assert calls[0] == (
        [
            str(binary),
            'install',
            '--force',
            'controller',
            '--config',
            str(config),
            '--data-dir',
            '/var/lib/k0s',
            '--enable-worker',
        ],
        False,
    )
