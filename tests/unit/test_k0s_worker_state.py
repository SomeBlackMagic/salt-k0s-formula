import importlib.util


MODULE_PATH = '_states/k0s_worker.py'


def _load_state_module():
    spec = importlib.util.spec_from_file_location('k0s_worker', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__opts__ = {'test': False}
    module.__salt__ = {}
    module._systemd_available = lambda: True
    module._worker_install_supports_api_server = lambda binary: True
    return module


def _create_prerequisites(tmp_path):
    binary = tmp_path / 'k0s'
    token_file = tmp_path / 'join-token'

    binary.write_text('#!/bin/sh\n')
    binary.chmod(0o755)
    token_file.write_text('join-token\n')
    token_file.chmod(0o600)
    return binary, token_file


def _write_unit(unit_path, binary, token_file, api_server, profile, data_dir, extra_args=''):
    unit_path.write_text(
        '[Service]\n'
        'ExecStart={0} worker --token-file={1} --api-server={2} '
        '--profile={3} --data-dir={4}{5}\n'.format(
            binary,
            token_file,
            api_server,
            profile,
            data_dir,
            extra_args,
        )
    )


def test_installed_reports_pending_change_in_test_mode(tmp_path):
    state = _load_state_module()
    binary, token_file = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0sworker.service'
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.installed(
        'k0sworker',
        token_file=str(token_file),
        api_server='https://10.0.0.10:6443',
        profile='default',
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
    )

    assert result['result'] is None
    assert result['changes']['unit']['new'] == 'installed'
    assert calls == []


def test_installed_fails_clearly_when_token_file_is_missing(tmp_path):
    state = _load_state_module()
    binary = tmp_path / 'k0s'
    binary.write_text('#!/bin/sh\n')
    binary.chmod(0o755)

    result = state.installed(
        'k0sworker',
        token_file=str(tmp_path / 'missing-token'),
        api_server='https://10.0.0.10:6443',
        profile='default',
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(tmp_path / 'k0sworker.service'),
    )

    assert result['result'] is False
    assert 'Missing required file(s)' in result['comment']
    assert 'missing-token' in result['comment']


def test_installed_creates_unit_with_requested_arguments(tmp_path):
    state = _load_state_module()
    binary, token_file = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0sworker.service'
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        _write_unit(
            unit_path,
            binary,
            token_file,
            'https://10.0.0.10:6443',
            'default',
            '/var/lib/k0s',
            ' --debug',
        )
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.installed(
        'k0sworker',
        token_file=str(token_file),
        api_server='https://10.0.0.10:6443',
        profile='default',
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
        extra_args='--debug',
    )

    assert result['result'] is True
    assert result['changes']['unit']['old'] == 'missing'
    assert calls == [
        (
            [
                str(binary),
                'install',
                'worker',
                '--token-file',
                str(token_file),
                '--api-server',
                'https://10.0.0.10:6443',
                '--profile',
                'default',
                '--data-dir',
                '/var/lib/k0s',
                '--debug',
            ],
            False,
        )
    ]


def test_installed_is_idempotent_when_unit_matches(tmp_path):
    state = _load_state_module()
    binary, token_file = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0sworker.service'
    _write_unit(
        unit_path,
        binary,
        token_file,
        'https://10.0.0.10:6443',
        'default',
        '/var/lib/k0s',
    )
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.installed(
        'k0sworker',
        token_file=str(token_file),
        api_server='https://10.0.0.10:6443',
        profile='default',
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
    )

    assert result['result'] is True
    assert result['changes'] == {}
    assert calls == []


def test_installed_uses_force_when_existing_unit_arguments_change(tmp_path):
    state = _load_state_module()
    binary, token_file = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0sworker.service'
    _write_unit(
        unit_path,
        binary,
        token_file,
        'https://10.0.0.10:6443',
        'default',
        '/var/lib/k0s',
    )
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        _write_unit(
            unit_path,
            binary,
            token_file,
            'https://10.0.0.11:6443',
            'default',
            '/var/lib/k0s',
        )
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.installed(
        'k0sworker',
        token_file=str(token_file),
        api_server='https://10.0.0.11:6443',
        profile='default',
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
    )

    assert result['result'] is True
    assert calls[0] == (
        [
            str(binary),
            'install',
            '--force',
            'worker',
            '--token-file',
            str(token_file),
            '--api-server',
            'https://10.0.0.11:6443',
            '--profile',
            'default',
            '--data-dir',
            '/var/lib/k0s',
        ],
        False,
    )


def test_installed_adds_api_server_to_unit_when_install_command_does_not_support_it(tmp_path):
    state = _load_state_module()
    state._worker_install_supports_api_server = lambda binary: False
    binary, token_file = _create_prerequisites(tmp_path)
    unit_path = tmp_path / 'k0sworker.service'
    calls = []

    def run_all(command, python_shell):
        calls.append((command, python_shell))
        _write_unit(
            unit_path,
            binary,
            token_file,
            'https://from-token.example:6443',
            'default',
            '/var/lib/k0s',
        )
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.installed(
        'k0sworker',
        token_file=str(token_file),
        api_server='https://10.0.0.10:6443',
        profile='default',
        data_dir='/var/lib/k0s',
        binary=str(binary),
        unit_path=str(unit_path),
    )

    assert result['result'] is True
    assert calls == [
        (
            [
                str(binary),
                'install',
                'worker',
                '--token-file',
                str(token_file),
                '--profile',
                'default',
                '--data-dir',
                '/var/lib/k0s',
            ],
            False,
        )
    ]
    assert '--api-server https://10.0.0.10:6443' in unit_path.read_text()
