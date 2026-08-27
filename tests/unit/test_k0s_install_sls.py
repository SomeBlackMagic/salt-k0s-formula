import jinja2
import yaml


INSTALL_SLS_PATH = 'k0s/install.sls'
DEFAULT_VERSION = 'v1.30.2+k0s.0'
DEFAULT_BINARY_PATH = '/usr/local/bin/k0s'


def _render(pillar_data=None, grains_data=None):
    if pillar_data is None:
        pillar_data = {}
    if grains_data is None:
        grains_data = {'osarch': 'amd64'}

    env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))

    def pillar_get(key, default=None):
        keys = key.split(':')
        val = pillar_data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    template = env.get_template(INSTALL_SLS_PATH)
    return template.render(
        salt={'pillar.get': pillar_get},
        grains=grains_data,
    )


def _parsed(pillar_data=None, grains_data=None):
    return yaml.safe_load(_render(pillar_data, grains_data)) or {}


def _state_ids(pillar_data=None, grains_data=None):
    return set(_parsed(pillar_data, grains_data).keys())


def _params(state_id, pillar_data=None, grains_data=None):
    block = _parsed(pillar_data, grains_data)[state_id]
    module = list(block.keys())[0]
    return {k: v for item in (block[module] or []) for k, v in item.items()}


# --- architecture ---


def test_amd64_produces_three_install_states():
    ids = _state_ids(grains_data={'osarch': 'amd64'})
    assert 'k0s_binary_download' in ids
    assert 'k0s_binary_install' in ids
    assert 'k0s_binary_permissions' in ids


def test_arm64_produces_install_states():
    ids = _state_ids(grains_data={'osarch': 'arm64'})
    assert 'k0s_binary_download' in ids
    assert 'k0s_binary_install' in ids
    assert 'k0s_binary_permissions' in ids


def test_aarch64_maps_to_arm64_in_binary_name():
    rendered = _render(grains_data={'osarch': 'aarch64'})
    assert 'arm64' in rendered
    assert 'aarch64' not in rendered


def test_unsupported_architecture_produces_fail_state():
    ids = _state_ids(grains_data={'osarch': 'mips'})
    assert 'k0s_install_unsupported_architecture' in ids
    assert 'k0s_binary_download' not in ids
    assert 'k0s_binary_install' not in ids


def test_unsupported_architecture_fail_state_mentions_arch():
    rendered = _render(grains_data={'osarch': 'mips'})
    assert 'mips' in rendered


# --- binary URL ---


def test_default_binary_url_points_to_github_releases():
    params = _params('k0s_binary_download')
    assert 'github.com/k0sproject/k0s/releases/download' in params['source']


def test_default_binary_url_contains_version():
    params = _params('k0s_binary_download')
    assert DEFAULT_VERSION in params['source']


def test_default_binary_url_contains_arch():
    params = _params('k0s_binary_download')
    assert 'amd64' in params['source']


def test_custom_binary_url_overrides_github_default():
    pillar = {'k0s': {'install': {'binary_url': 'https://my.mirror/k0s'}}}
    params = _params('k0s_binary_download', pillar_data=pillar)
    assert params['source'] == 'https://my.mirror/k0s'


def test_custom_version_appears_in_download_url():
    pillar = {'k0s': {'version': 'v1.29.0+k0s.0'}}
    params = _params('k0s_binary_download', pillar_data=pillar)
    assert 'v1.29.0+k0s.0' in params['source']


def test_custom_version_does_not_keep_default_version_in_url():
    pillar = {'k0s': {'version': 'v1.29.0+k0s.0'}}
    params = _params('k0s_binary_download', pillar_data=pillar)
    assert DEFAULT_VERSION not in params['source']


# --- checksum ---


def test_no_checksum_sets_skip_verify():
    params = _params('k0s_binary_download')
    assert params.get('skip_verify') is True
    assert 'source_hash' not in params


def test_checksum_is_included_in_source_hash():
    pillar = {'k0s': {'install': {'checksum': 'deadbeef'}}}
    params = _params('k0s_binary_download', pillar_data=pillar)
    assert 'source_hash' in params
    assert 'deadbeef' in params['source_hash']


def test_checksum_disables_skip_verify():
    pillar = {'k0s': {'install': {'checksum': 'deadbeef'}}}
    params = _params('k0s_binary_download', pillar_data=pillar)
    assert 'skip_verify' not in params


# --- file destinations ---


def test_binary_is_installed_to_usr_local_bin():
    params = _params('k0s_binary_install')
    assert params['name'] == DEFAULT_BINARY_PATH


def test_binary_permissions_manage_usr_local_bin():
    params = _params('k0s_binary_permissions')
    assert params['name'] == DEFAULT_BINARY_PATH


def test_all_states_set_mode_0755():
    for state_id in ('k0s_binary_download', 'k0s_binary_install', 'k0s_binary_permissions'):
        params = _params(state_id)
        assert params['mode'] == '0755', f'{state_id} has wrong mode'


def test_all_states_set_owner_root():
    for state_id in ('k0s_binary_download', 'k0s_binary_install', 'k0s_binary_permissions'):
        params = _params(state_id)
        assert params['user'] == 'root', f'{state_id} has wrong user'
        assert params['group'] == 'root', f'{state_id} has wrong group'


# --- tmp download path ---


def test_download_path_is_in_tmp():
    params = _params('k0s_binary_download')
    assert params['name'].startswith('/tmp/')


def test_download_filename_contains_version():
    params = _params('k0s_binary_download')
    assert DEFAULT_VERSION in params['name']


def test_download_filename_contains_arch():
    params = _params('k0s_binary_download')
    assert 'amd64' in params['name']


def test_install_source_matches_download_destination():
    download_params = _params('k0s_binary_download')
    install_params = _params('k0s_binary_install')
    assert install_params['source'] == download_params['name']
