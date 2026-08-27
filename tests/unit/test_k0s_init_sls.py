import jinja2
import yaml


INIT_SLS_PATH = 'k0s/init.sls'


def _render(pillar_data=None):
    if pillar_data is None:
        pillar_data = {}

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

    template = env.get_template(INIT_SLS_PATH)
    return template.render(salt={'pillar.get': pillar_get})


def _includes(pillar_data=None):
    parsed = yaml.safe_load(_render(pillar_data)) or {}
    return parsed.get('include', [])


# --- always included regardless of role ---


def test_install_included_for_single():
    assert 'k0s.install' in _includes({'k0s': {'role': 'single'}})


def test_install_included_for_controller():
    assert 'k0s.install' in _includes({'k0s': {'role': 'controller'}})


def test_install_included_for_worker():
    assert 'k0s.install' in _includes({'k0s': {'role': 'worker'}})


def test_service_included_for_single():
    assert 'k0s.service' in _includes({'k0s': {'role': 'single'}})


def test_service_included_for_controller():
    assert 'k0s.service' in _includes({'k0s': {'role': 'controller'}})


def test_service_included_for_worker():
    assert 'k0s.service' in _includes({'k0s': {'role': 'worker'}})


def test_manifest_included_for_single():
    assert 'k0s.manifest' in _includes({'k0s': {'role': 'single'}})


def test_manifest_included_for_controller():
    assert 'k0s.manifest' in _includes({'k0s': {'role': 'controller'}})


def test_manifest_included_for_worker():
    assert 'k0s.manifest' in _includes({'k0s': {'role': 'worker'}})


# --- role-specific includes ---


def test_single_role_includes_config():
    assert 'k0s.config' in _includes({'k0s': {'role': 'single'}})


def test_single_role_includes_controller():
    assert 'k0s.controller' in _includes({'k0s': {'role': 'single'}})


def test_controller_role_includes_config():
    assert 'k0s.config' in _includes({'k0s': {'role': 'controller'}})


def test_controller_role_includes_controller():
    assert 'k0s.controller' in _includes({'k0s': {'role': 'controller'}})


def test_worker_role_includes_worker():
    assert 'k0s.worker' in _includes({'k0s': {'role': 'worker'}})


# --- default role ---


def test_default_role_is_single_includes_config():
    assert 'k0s.config' in _includes({})


def test_default_role_is_single_includes_controller():
    assert 'k0s.controller' in _includes({})


def test_default_role_does_not_include_worker():
    assert 'k0s.worker' not in _includes({})


# --- role-specific exclusions ---


def test_single_role_does_not_include_worker():
    assert 'k0s.worker' not in _includes({'k0s': {'role': 'single'}})


def test_controller_role_does_not_include_worker():
    assert 'k0s.worker' not in _includes({'k0s': {'role': 'controller'}})


def test_worker_role_does_not_include_config():
    assert 'k0s.config' not in _includes({'k0s': {'role': 'worker'}})


def test_worker_role_does_not_include_controller_module():
    assert 'k0s.controller' not in _includes({'k0s': {'role': 'worker'}})


# --- ordering ---


def test_install_comes_before_service_for_single():
    includes = _includes({'k0s': {'role': 'single'}})
    assert includes.index('k0s.install') < includes.index('k0s.service')


def test_install_comes_before_manifest_for_single():
    includes = _includes({'k0s': {'role': 'single'}})
    assert includes.index('k0s.install') < includes.index('k0s.manifest')
