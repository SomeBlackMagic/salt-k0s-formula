import glob
import os

import pytest
import testinfra
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _get_kitchen_state():
    suite = os.environ.get('KITCHEN_SUITE', 'default')
    platform = os.environ.get('KITCHEN_PLATFORM', 'ubuntu')
    state_file = os.path.join(BASE_DIR, '.kitchen', f'{suite}-{platform}.yml')

    if os.path.exists(state_file):
        with open(state_file) as f:
            return yaml.safe_load(f) or {}

    # Fallback: find any running instance
    for path in glob.glob(os.path.join(BASE_DIR, '.kitchen', '*.yml')):
        try:
            with open(path) as f:
                state = yaml.safe_load(f)
            if state and state.get('container_id'):
                return state
        except Exception:
            continue
    return {}


@pytest.fixture(scope='session')
def host(tmp_path_factory):
    # CI mode: connect directly to a named Docker container.
    docker_container = os.environ.get('KITCHEN_DOCKER_CONTAINER')
    if docker_container:
        return testinfra.get_host(f'docker://{docker_container}')

    # Local mode: connect via SSH to a Kitchen-managed container.
    state = _get_kitchen_state()
    username = state.get('username', 'kitchen')
    hostname = state.get('hostname', 'localhost')
    port = state.get('port', 22)
    ssh_key = state.get('ssh_key', os.path.join(BASE_DIR, '.kitchen', 'docker_id_rsa'))

    ssh_config = tmp_path_factory.mktemp('ssh') / 'config'
    ssh_config.write_text(
        f'Host {hostname}\n'
        f'    StrictHostKeyChecking no\n'
        f'    UserKnownHostsFile /dev/null\n'
    )

    return testinfra.get_host(
        f'ssh://{username}@{hostname}:{port}',
        ssh_identity_file=ssh_key,
        ssh_config=str(ssh_config),
    )
