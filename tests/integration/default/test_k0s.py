import json

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


def _changed_states(result):
    return {
        state_id: state_result.get('changes')
        for state_id, state_result in result.get('local', {}).items()
        if state_result.get('changes')
    }


def _k0s_config(host):
    config_file = host.file('/etc/k0s/k0s.yaml')
    result = host.run('sudo cat /etc/k0s/k0s.yaml')

    assert config_file.exists
    assert result.rc == 0, result.stderr
    return yaml.safe_load(result.stdout)


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
    assert 'k0s_controller_placeholder' in state_ids
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


def test_k0s_install_is_idempotent(host):
    result = _apply_k0s_state(host)

    assert _changed_states(result) == {}
