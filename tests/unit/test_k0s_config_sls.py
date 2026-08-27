import jinja2
import yaml


CONFIG_SLS_PATH = 'k0s/config.sls'
DEFAULT_CONFIG_PATH = '/etc/k0s/k0s.yaml'
DEFAULT_CONFIG_DIR = '/etc/k0s'


def _render(pillar_data=None):
    if pillar_data is None:
        pillar_data = {}

    env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
    # PyYAML 6.x appends '...\n' (document end marker) after root-level scalars.
    # Strip it so the rendered SLS remains valid YAML.
    env.filters['yaml'] = lambda v: yaml.safe_dump(
        v, default_flow_style=None
    ).replace('\n...\n', '\n').strip()

    def pillar_get(key, default=None):
        keys = key.split(':')
        val = pillar_data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    template = env.get_template(CONFIG_SLS_PATH)
    return template.render(salt={'pillar.get': pillar_get})


def _parsed(pillar_data=None):
    return yaml.safe_load(_render(pillar_data)) or {}


def _state_ids(pillar_data=None):
    return set(_parsed(pillar_data).keys()) - {'include'}


def _state_module(state_id, pillar_data=None):
    block = _parsed(pillar_data)[state_id]
    return list(block.keys())[0]


def _params(state_id, pillar_data=None):
    block = _parsed(pillar_data)[state_id]
    module = list(block.keys())[0]
    return {k: v for item in (block[module] or []) for k, v in item.items()}


# --- states produced ---


def test_config_directory_state_always_produced():
    assert 'k0s_config_directory' in _state_ids()


def test_config_file_state_always_produced():
    assert 'k0s_config_file' in _state_ids()


def test_config_create_state_produced_when_no_spec():
    assert 'k0s_config_create' in _state_ids()


def test_config_create_state_absent_when_spec_provided():
    pillar = {'k0s': {'config': {'spec': {'network': {'provider': 'kuberouter'}}}}}
    assert 'k0s_config_create' not in _state_ids(pillar)


# --- include ---


def test_include_references_k0s_install():
    parsed = _parsed()
    assert 'k0s.install' in parsed.get('include', [])


# --- config directory ---


def test_default_config_dir_path():
    assert _params('k0s_config_directory')['name'] == DEFAULT_CONFIG_DIR


def test_custom_config_path_derives_correct_dir():
    pillar = {'k0s': {'config_path': '/opt/k0s/config/k0s.yaml'}}
    assert _params('k0s_config_directory', pillar)['name'] == '/opt/k0s/config'


def test_nested_custom_config_path_derives_correct_dir():
    pillar = {'k0s': {'config_path': '/etc/k0s/cluster/node.yaml'}}
    assert _params('k0s_config_directory', pillar)['name'] == '/etc/k0s/cluster'


def test_config_directory_mode_is_0755():
    assert _params('k0s_config_directory')['mode'] == '0755'


def test_config_directory_owner_is_root():
    params = _params('k0s_config_directory')
    assert params['user'] == 'root'
    assert params['group'] == 'root'


# --- config file (no spec) ---


def test_config_file_default_path():
    assert _params('k0s_config_file')['name'] == DEFAULT_CONFIG_PATH


def test_config_file_mode_is_0600():
    assert _params('k0s_config_file')['mode'] == '0600'


def test_config_file_owner_is_root():
    params = _params('k0s_config_file')
    assert params['user'] == 'root'
    assert params['group'] == 'root'


def test_config_file_without_spec_has_no_source():
    assert 'source' not in _params('k0s_config_file')


def test_config_file_without_spec_has_no_template():
    assert 'template' not in _params('k0s_config_file')


# --- config file (with spec) ---


def _spec_pillar():
    return {'k0s': {'config': {'spec': {'network': {'provider': 'kuberouter'}}}}}


def test_config_file_with_spec_uses_jinja_source():
    params = _params('k0s_config_file', _spec_pillar())
    assert 'source' in params
    assert 'k0s.yaml.j2' in params['source']


def test_config_file_with_spec_uses_jinja_template_engine():
    assert _params('k0s_config_file', _spec_pillar()).get('template') == 'jinja'


def test_config_file_with_spec_has_correct_mode():
    assert _params('k0s_config_file', _spec_pillar())['mode'] == '0600'


def test_config_file_with_spec_uses_custom_path():
    pillar = {'k0s': {
        'config_path': '/opt/k0s/k0s.yaml',
        'config': {'spec': {'network': {'provider': 'kuberouter'}}},
    }}
    assert _params('k0s_config_file', pillar)['name'] == '/opt/k0s/k0s.yaml'


# --- k0s_config_create state ---


def test_config_create_uses_k0s_config_module():
    assert _state_module('k0s_config_create') == 'k0s_config.created'


def test_config_create_uses_default_config_path():
    assert _params('k0s_config_create')['name'] == DEFAULT_CONFIG_PATH


def test_config_create_uses_custom_config_path():
    pillar = {'k0s': {'config_path': '/opt/k0s/k0s.yaml'}}
    assert _params('k0s_config_create', pillar)['name'] == '/opt/k0s/k0s.yaml'
