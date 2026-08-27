import jinja2
import yaml


SERVICE_SLS_PATH = 'k0s/service.sls'


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

    template = env.get_template(SERVICE_SLS_PATH)
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


def _worker_pillar(running=True, enabled=True):
    return {'k0s': {
        'role': 'worker',
        'service': {'running': running, 'enabled': enabled},
        'worker': {'join_token': 'test-token', 'api_address': '10.0.0.1:6443'},
    }}


# --- service name by role ---


def test_single_role_uses_k0scontroller():
    assert _params('k0s_service', {'k0s': {'role': 'single'}})['name'] == 'k0scontroller'


def test_controller_role_uses_k0scontroller():
    assert _params('k0s_service', {'k0s': {'role': 'controller'}})['name'] == 'k0scontroller'


def test_worker_role_uses_k0sworker():
    assert _params('k0s_service', _worker_pillar())['name'] == 'k0sworker'


def test_default_role_is_single():
    assert _params('k0s_service')['name'] == 'k0scontroller'


# --- service state module ---


def test_service_running_by_default():
    assert _state_module('k0s_service') == 'service.running'


def test_service_dead_when_running_false():
    pillar = {'k0s': {'service': {'running': False, 'enabled': False}}}
    assert _state_module('k0s_service', pillar) == 'service.dead'


def test_service_running_when_only_enabled_is_false():
    pillar = {'k0s': {'service': {'running': True, 'enabled': False}}}
    assert _state_module('k0s_service', pillar) == 'service.running'


# --- enable flag ---


def test_service_enabled_true_by_default():
    assert _params('k0s_service')['enable'] is True


def test_service_enabled_false_when_set_in_pillar():
    pillar = {'k0s': {'service': {'enabled': False}}}
    assert _params('k0s_service', pillar)['enable'] is False


def test_service_dead_has_enable_false():
    pillar = {'k0s': {'service': {'running': False, 'enabled': False}}}
    assert _params('k0s_service', pillar)['enable'] is False


# --- cluster operational state ---


def test_controller_operational_produced_for_single_role():
    assert 'k0s_controller_operational' in _state_ids({'k0s': {'role': 'single'}})


def test_controller_operational_produced_for_controller_role():
    assert 'k0s_controller_operational' in _state_ids({'k0s': {'role': 'controller'}})


def test_controller_operational_not_produced_for_worker_role():
    assert 'k0s_controller_operational' not in _state_ids(_worker_pillar())


def test_controller_operational_not_produced_when_service_dead():
    pillar = {'k0s': {'role': 'single', 'service': {'running': False}}}
    assert 'k0s_controller_operational' not in _state_ids(pillar)


def test_controller_operational_uses_k0s_cluster_module():
    assert _state_module('k0s_controller_operational') == 'k0s_cluster.operational'


# --- unknown role ---


def test_unknown_role_produces_fail_state():
    pillar = {'k0s': {'role': 'banana'}}
    assert 'k0s_service_unknown_role' in _state_ids(pillar)
    assert 'k0s_service' not in _state_ids(pillar)


def test_unknown_role_fail_state_mentions_the_role():
    assert 'banana' in _render({'k0s': {'role': 'banana'}})


def test_unknown_role_fail_state_uses_test_module():
    pillar = {'k0s': {'role': 'banana'}}
    assert _state_module('k0s_service_unknown_role', pillar) == 'test.fail_without_changes'


# --- worker without required tokens ---


def test_worker_without_join_token_produces_no_service_state():
    pillar = {'k0s': {'role': 'worker', 'worker': {'api_address': '10.0.0.1:6443'}}}
    assert 'k0s_service' not in _state_ids(pillar)


def test_worker_without_api_address_produces_no_service_state():
    pillar = {'k0s': {'role': 'worker', 'worker': {'join_token': 'token'}}}
    assert 'k0s_service' not in _state_ids(pillar)


def test_worker_without_any_tokens_produces_no_service_state():
    assert 'k0s_service' not in _state_ids({'k0s': {'role': 'worker'}})


def test_worker_with_both_tokens_produces_service_state():
    assert 'k0s_service' in _state_ids(_worker_pillar())


# --- includes ---


def test_single_role_includes_controller():
    assert 'k0s.controller' in _parsed({'k0s': {'role': 'single'}}).get('include', [])


def test_controller_role_includes_controller():
    assert 'k0s.controller' in _parsed({'k0s': {'role': 'controller'}}).get('include', [])


def test_worker_role_includes_worker():
    assert 'k0s.worker' in _parsed(_worker_pillar()).get('include', [])


def test_single_role_does_not_include_worker():
    assert 'k0s.worker' not in _parsed({'k0s': {'role': 'single'}}).get('include', [])


def test_worker_role_does_not_include_controller():
    assert 'k0s.controller' not in _parsed(_worker_pillar()).get('include', [])
