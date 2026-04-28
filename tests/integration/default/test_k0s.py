import json

import pytest
import yaml


SALT_CALL = (
    'sudo salt-call --local '
    '--file-root=/tmp/kitchen/srv/salt '
    '--pillar-root=/tmp/kitchen/srv/pillar '
)
K0S_VERSION = 'v1.30.2+k0s.0'


def _apply_k0s_state(host):
    result = host.run(f'{SALT_CALL} state.apply k0s --out=json')

    assert result.rc == 0, result.stderr
    return json.loads(result.stdout)


def _apply_k0s_state_with_pillar(host, pillar):
    pillar_json = json.dumps(pillar)
    result = host.run(f"{SALT_CALL} state.apply k0s pillar='{pillar_json}' --out=json")

    assert result.rc == 0, result.stderr
    return json.loads(result.stdout)


def _apply_k0s_token_state(host, pillar=None):
    pillar_arg = ''
    if pillar is not None:
        pillar_arg = " pillar='{0}'".format(json.dumps(pillar))

    result = host.run(f'{SALT_CALL} state.apply k0s.token{pillar_arg} --out=json')

    assert result.rc == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope='session', autouse=True)
def synced_states(host):
    result = host.run(f'{SALT_CALL} saltutil.sync_states')

    assert result.rc == 0, result.stderr


def _changed_states(result):
    return {
        state_id: state_result.get('changes')
        for state_id, state_result in result.get('local', {}).items()
        if state_result.get('changes')
    }


def _changed_state_ids(result):
    return {
        state_result.get('__id__')
        for state_result in result.get('local', {}).values()
        if state_result.get('changes')
    }


def _k0s_config(host):
    config_file = host.file('/etc/k0s/k0s.yaml')
    result = host.run('sudo cat /etc/k0s/k0s.yaml')

    assert config_file.exists
    assert result.rc == 0, result.stderr
    return yaml.safe_load(result.stdout)


def _k0s_controller_unit(host):
    unit_file = host.file('/etc/systemd/system/k0scontroller.service')
    result = host.run('sudo cat /etc/systemd/system/k0scontroller.service')

    assert unit_file.exists
    assert result.rc == 0, result.stderr
    return result.stdout


def _k0s_worker_unit(host):
    unit_file = host.file('/etc/systemd/system/k0sworker.service')
    result = host.run('sudo cat /etc/systemd/system/k0sworker.service')

    assert unit_file.exists
    assert result.rc == 0, result.stderr
    return result.stdout


def _systemctl(host, command, service):
    return host.run(f'sudo systemctl {command} {service}')


def test_salt_installed(host):
    assert host.package('salt-minion').is_installed


def test_k0s_states_succeed(host):
    result = _apply_k0s_state(host)
    state_ids = {
        state_result.get('__id__')
        for state_result in result.get('local', {}).values()
    }

    assert 'k0s_binary_download' in state_ids
    assert 'k0s_binary_install' in state_ids
    assert 'k0s_binary_permissions' in state_ids
    assert 'k0s_config_directory' in state_ids
    assert 'k0s_config_file' in state_ids
    assert 'k0s_controller_unit' in state_ids
    assert 'k0s_service' in state_ids


def test_k0s_binary_is_installed(host):
    binary = host.file('/usr/local/bin/k0s')

    assert binary.exists
    assert binary.is_file
    assert binary.user == 'root'
    assert binary.group == 'root'
    assert binary.mode == 0o755


def test_k0s_version_matches_pillar(host):
    result = host.run('/usr/local/bin/k0s version')

    assert result.rc == 0
    assert K0S_VERSION in result.stdout


def test_k0s_config_file_is_managed(host):
    config_file = host.file('/etc/k0s/k0s.yaml')

    assert config_file.exists
    assert config_file.is_file
    assert config_file.user == 'root'
    assert config_file.group == 'root'
    assert config_file.mode == 0o600


def test_k0s_config_values_match_pillar(host):
    config = _k0s_config(host)

    assert config['apiVersion'] == 'k0s.k0sproject.io/v1beta1'
    assert config['kind'] == 'ClusterConfig'
    assert config['metadata']['name'] == 'k0s'
    assert config['spec']['network']['provider'] == 'kuberouter'
    assert config['spec']['network']['podCIDR'] == '10.244.0.0/16'
    assert config['spec']['network']['serviceCIDR'] == '10.96.0.0/12'
    assert config['spec']['storage']['type'] == 'etcd'
    assert config['spec']['telemetry']['enabled'] is False


def test_k0s_config_api_address_is_resolved(host):
    config = _k0s_config(host)
    api_address = config['spec']['api']['address']

    assert api_address
    assert not api_address.startswith('127.')
    assert config['spec']['api']['sans'][0] == api_address
    assert 'k0s.local' in config['spec']['api']['sans']


def test_k0s_config_is_valid(host):
    result = host.run('sudo /usr/local/bin/k0s config validate --config /etc/k0s/k0s.yaml')

    assert result.rc == 0, result.stderr


def test_k0s_controller_unit_is_installed(host):
    unit_file = host.file('/etc/systemd/system/k0scontroller.service')
    unit_content = _k0s_controller_unit(host)

    assert unit_file.exists
    assert unit_file.is_file
    assert unit_file.user == 'root'
    assert unit_file.group == 'root'
    assert 'ExecStart=' in unit_content
    assert '--config' in unit_content
    assert '/etc/k0s/k0s.yaml' in unit_content
    assert '--data-dir' in unit_content
    assert '/var/lib/k0s' in unit_content


def test_k0s_controller_service_is_enabled_and_running(host):
    _apply_k0s_state(host)

    active = _systemctl(host, 'is-active', 'k0scontroller')
    enabled = _systemctl(host, 'is-enabled', 'k0scontroller')

    assert active.rc == 0, active.stdout + active.stderr
    assert active.stdout.strip() == 'active'
    assert enabled.rc == 0, enabled.stdout + enabled.stderr
    assert enabled.stdout.strip() == 'enabled'


def test_k0s_controller_flags_are_installed_from_pillar(host):
    _apply_k0s_state_with_pillar(
        host,
        {
            'k0s': {
                'controller': {
                    'enable_worker': True,
                    'no_taints': True,
                },
            },
        },
    )
    unit_content = _k0s_controller_unit(host)

    assert '--enable-worker' in unit_content
    assert '--no-taints' in unit_content


def test_k0s_controller_test_mode_does_not_apply_changes(host):
    result = host.run(f'{SALT_CALL} state.apply k0s test=True --out=json')

    assert result.rc == 0, result.stderr
    state_result = next(
        value
        for value in json.loads(result.stdout).get('local', {}).values()
        if value.get('__id__') == 'k0s_controller_unit'
    )
    assert state_result['result'] is True
    assert state_result['changes'] == {}


def test_k0s_controller_service_can_be_stopped_and_disabled(host):
    _apply_k0s_state_with_pillar(
        host,
        {
            'k0s': {
                'service': {
                    'enabled': False,
                    'running': False,
                },
            },
        },
    )

    active = _systemctl(host, 'is-active', 'k0scontroller')
    enabled = _systemctl(host, 'is-enabled', 'k0scontroller')

    assert active.rc != 0
    assert active.stdout.strip() == 'inactive'
    assert enabled.rc != 0
    assert enabled.stdout.strip() == 'disabled'

    _apply_k0s_state(host)


def test_k0s_worker_role_writes_token_and_installs_unit(host):
    result = _apply_k0s_state_with_pillar(
        host,
        {
            'k0s': {
                'role': 'worker',
                'service': {
                    'enabled': False,
                    'running': False,
                },
                'worker': {
                    'join_token': 'test-worker-token',
                    'api_address': '10.0.0.10:6443',
                    'profile': 'default',
                },
            },
        },
    )
    token_file = host.file('/etc/k0s/join-token')
    unit_content = _k0s_worker_unit(host)

    assert token_file.exists
    assert token_file.is_file
    assert token_file.user == 'root'
    assert token_file.group == 'root'
    assert token_file.mode == 0o600
    token_content = host.run('sudo cat /etc/k0s/join-token')

    assert token_content.rc == 0, token_content.stderr
    assert token_content.stdout.rstrip('\n') == 'test-worker-token'
    assert 'k0s_worker_join_token' in {
        state_result.get('__id__')
        for state_result in result.get('local', {}).values()
    }
    assert 'ExecStart=' in unit_content
    assert '--token-file' in unit_content
    assert '/etc/k0s/join-token' in unit_content
    assert '--api-server' in unit_content
    assert 'https://10.0.0.10:6443' in unit_content
    assert '--profile' in unit_content
    assert 'default' in unit_content
    assert '--data-dir' in unit_content
    assert '/var/lib/k0s' in unit_content


def test_k0s_worker_validation_fails_without_required_pillars(host):
    result = host.run(
        f"{SALT_CALL} state.apply k0s pillar='{{\"k0s\": {{\"role\": \"worker\"}}}}' --out=json"
    )
    state_result = json.loads(result.stdout)
    messages = [
        '{0} {1}'.format(value.get('name', ''), value.get('comment', ''))
        for value in state_result.get('local', {}).values()
    ]

    assert result.rc != 0
    assert any('k0s.worker.join_token is required' in message for message in messages)
    assert any('k0s.worker.api_address is required' in message for message in messages)


def test_k0s_worker_install_is_idempotent(host):
    _apply_k0s_state_with_pillar(
        host,
        {
            'k0s': {
                'role': 'worker',
                'service': {
                    'enabled': False,
                    'running': False,
                },
                'worker': {
                    'join_token': 'test-worker-token',
                    'api_address': '10.0.0.10:6443',
                    'profile': 'default',
                },
            },
        },
    )
    result = _apply_k0s_state_with_pillar(
        host,
        {
            'k0s': {
                'role': 'worker',
                'service': {
                    'enabled': False,
                    'running': False,
                },
                'worker': {
                    'join_token': 'test-worker-token',
                    'api_address': '10.0.0.10:6443',
                    'profile': 'default',
                },
            },
        },
    )

    assert _changed_states(result) == {}


def test_k0s_token_state_creates_worker_join_token(host):
    _apply_k0s_token_state(host)
    token_file = host.file('/etc/k0s/worker-join-token')
    token_content = host.run('sudo cat /etc/k0s/worker-join-token')

    assert token_file.exists
    assert token_file.is_file
    assert token_file.user == 'root'
    assert token_file.group == 'root'
    assert token_file.mode == 0o600
    assert token_content.rc == 0, token_content.stderr
    assert token_content.stdout.strip()


def test_k0s_token_state_is_idempotent_within_ttl(host):
    _apply_k0s_token_state(host)
    result = _apply_k0s_token_state(host)

    assert _changed_states(result) == {}


def test_k0s_token_state_regenerates_expired_token(host):
    _apply_k0s_token_state(host, {'k0s': {'token': {'ttl': 1}}})
    before = host.run('sudo stat -c %Y /etc/k0s/worker-join-token')

    assert before.rc == 0, before.stderr

    touch = host.run('sudo touch -d "2 hours ago" /etc/k0s/worker-join-token')

    assert touch.rc == 0, touch.stderr

    result = _apply_k0s_token_state(host, {'k0s': {'token': {'ttl': 1}}})
    after = host.run('sudo stat -c %Y /etc/k0s/worker-join-token')

    assert after.rc == 0, after.stderr
    assert int(after.stdout.strip()) > int(before.stdout.strip())
    assert 'k0s_worker_join_token_create' in _changed_state_ids(result)


def test_k0s_install_is_idempotent(host):
    result = _apply_k0s_state(host)

    assert _changed_states(result) == {}
