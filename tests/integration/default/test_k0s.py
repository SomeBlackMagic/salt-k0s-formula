import json


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
    assert 'k0s_config_placeholder' in state_ids
    assert 'k0s_controller_placeholder' in state_ids
    assert 'k0s_service_placeholder' in state_ids


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


def test_k0s_install_is_idempotent(host):
    result = _apply_k0s_state(host)

    assert _changed_states(result) == {}
