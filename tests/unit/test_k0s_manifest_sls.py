import jinja2
import pytest
import yaml


MANIFEST_SLS_PATH = 'k0s/manifest.sls'
DEFAULT_BINARY = '/usr/local/bin/k0s'


def _render(pillar_data):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('.'),
        extensions=['jinja2.ext.do'],
    )

    def pillar_get(key, default=None):
        keys = key.split(':')
        val = pillar_data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    template = env.get_template(MANIFEST_SLS_PATH)
    return template.render(salt={'pillar.get': pillar_get})


def _state_ids(rendered):
    """Return top-level state IDs from rendered SLS (YAML keys)."""
    parsed = yaml.safe_load(rendered)
    if not parsed:
        return set()
    return set(parsed.keys())


def _state_block(rendered, state_id):
    parsed = yaml.safe_load(rendered)
    return parsed[state_id]


# --- empty manifests ---


def test_no_manifests_renders_empty(tmp_path):
    rendered = _render({'k0s': {}})

    assert yaml.safe_load(rendered) is None


def test_empty_list_renders_empty(tmp_path):
    rendered = _render({'k0s': {'manifests': []}})

    assert yaml.safe_load(rendered) is None


def test_empty_dict_renders_empty(tmp_path):
    rendered = _render({'k0s': {'manifests': {}}})

    assert yaml.safe_load(rendered) is None


# --- list format ---


def test_list_single_manifest_produces_state_id_from_name(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    assert 'k0s_manifest_my-crds' in _state_ids(rendered)


def test_list_manifest_name_appears_in_state_name_field(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    block = _state_block(rendered, 'k0s_manifest_my-crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['name'] == 'my-crds'


def test_list_multiple_manifests_produce_distinct_state_ids(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
        {'name': 'connectors', 'source': '/srv/salt/connectors.yaml'},
    ]}})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_crds' in ids
    assert 'k0s_manifest_connectors' in ids


def test_list_manifest_source_is_passed_through(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    block = _state_block(rendered, 'k0s_manifest_crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['source'] == '/srv/salt/crds.yaml'


def test_list_manifest_wait_is_passed_through(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {
            'name': 'crds',
            'source': '/srv/salt/crds.yaml',
            'wait': [{'for': 'condition=Established', 'resource': 'crd/foo'}],
        },
    ]}})

    block = _state_block(rendered, 'k0s_manifest_crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['wait'] == [{'for': 'condition=Established', 'resource': 'crd/foo'}]


def test_list_manifest_without_source_omits_source_param(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {'name': 'inline', 'content': 'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: test\n'},
    ]}})

    block = _state_block(rendered, 'k0s_manifest_inline')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert 'source' not in params


# --- dict format ---


def test_dict_key_becomes_state_id(tmp_path):
    rendered = _render({'k0s': {'manifests': {
        'my-crds': {'source': '/srv/salt/crds.yaml'},
    }}})

    assert 'k0s_manifest_my-crds' in _state_ids(rendered)


def test_dict_key_becomes_name_field(tmp_path):
    rendered = _render({'k0s': {'manifests': {
        'my-crds': {'source': '/srv/salt/crds.yaml'},
    }}})

    block = _state_block(rendered, 'k0s_manifest_my-crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['name'] == 'my-crds'


def test_dict_multiple_keys_produce_distinct_state_ids(tmp_path):
    rendered = _render({'k0s': {'manifests': {
        'crds': {'source': '/srv/salt/crds.yaml'},
        'connectors': {'source': '/srv/salt/connectors.yaml'},
    }}})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_crds' in ids
    assert 'k0s_manifest_connectors' in ids


def test_dict_source_is_passed_through(tmp_path):
    rendered = _render({'k0s': {'manifests': {
        'crds': {'source': '/srv/salt/crds.yaml'},
    }}})

    block = _state_block(rendered, 'k0s_manifest_crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['source'] == '/srv/salt/crds.yaml'


def test_dict_wait_is_passed_through(tmp_path):
    rendered = _render({'k0s': {'manifests': {
        'crds': {
            'source': '/srv/salt/crds.yaml',
            'wait': [{'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'}],
        },
    }}})

    block = _state_block(rendered, 'k0s_manifest_crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['wait'] == [{'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'}]


def test_dict_key_overrides_name_field_in_value(tmp_path):
    """If the value has a 'name' field, the dict key must take precedence."""
    rendered = _render({'k0s': {'manifests': {
        'actual-name': {'name': 'ignored-name', 'source': '/srv/salt/crds.yaml'},
    }}})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_actual-name' in ids
    assert 'k0s_manifest_ignored-name' not in ids

    block = _state_block(rendered, 'k0s_manifest_actual-name')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['name'] == 'actual-name'


def test_dict_content_and_source_and_wait_all_passed_through(tmp_path):
    """Full real-world example: CRDs in source, connector in content, with wait."""
    rendered = _render({'k0s': {'manifests': {
        'external-secrets-connectors': {
            'source': '/etc/k0s/external-secrets-connectors.yaml',
            'content': 'apiVersion: external-secrets.io/v1\nkind: ClusterSecretStore\n',
            'wait': [{'for': 'condition=Established',
                      'resource': 'crd/clustersecretstores.external-secrets.io',
                      'timeout': '60s'}],
        },
    }}})

    block = _state_block(rendered, 'k0s_manifest_external-secrets-connectors')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['name'] == 'external-secrets-connectors'
    assert params['source'] == '/etc/k0s/external-secrets-connectors.yaml'
    assert 'ClusterSecretStore' in params['content']
    assert params['wait'][0]['resource'] == 'crd/clustersecretstores.external-secrets.io'


# --- binary ---


def test_default_binary_is_used_when_not_in_pillar(tmp_path):
    rendered = _render({'k0s': {'manifests': [
        {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    block = _state_block(rendered, 'k0s_manifest_crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['binary'] == DEFAULT_BINARY


def test_custom_binary_from_pillar_is_used(tmp_path):
    rendered = _render({'k0s': {
        'binary': '/opt/k0s/bin/k0s',
        'manifests': [{'name': 'crds', 'source': '/srv/salt/crds.yaml'}],
    }})

    block = _state_block(rendered, 'k0s_manifest_crds')
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    assert params['binary'] == '/opt/k0s/bin/k0s'


# --- base64 content integrity ---
#
# Guard against template rendering corrupting base64 values in Secrets.
# The `indent` filter must not split or modify values on long lines.

_B64_TOKEN = 'c29tZXZlcnlsb25nYmFzZTY0ZW5jb2RlZHN0cmluZw=='

_SECRET_CONTENT = (
    'apiVersion: v1\n'
    'kind: Secret\n'
    'metadata:\n'
    '  name: my-secret\n'
    'data:\n'
    f'  token: {_B64_TOKEN}\n'
)


def _extract_content(rendered, state_id):
    block = _state_block(rendered, state_id)
    params = {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}
    return params['content']


def test_content_base64_value_preserved_in_list_format():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-secrets', 'content': _SECRET_CONTENT},
    ]}})
    content = _extract_content(rendered, 'k0s_manifest_my-secrets')

    assert f'token: {_B64_TOKEN}' in content


def test_content_base64_value_preserved_in_dict_format():
    rendered = _render({'k0s': {'manifests': {
        'my-secrets': {'content': _SECRET_CONTENT},
    }}})
    content = _extract_content(rendered, 'k0s_manifest_my-secrets')

    assert f'token: {_B64_TOKEN}' in content


def test_content_long_base64_value_is_not_line_wrapped():
    """Long values (e.g. k8s service account tokens) must not be split across lines."""
    long_token = 'eyJhbGciOiJSUzI1NiIsImtpZCI6IiJ9.' + 'A' * 200 + '.signature'
    content = f'apiVersion: v1\nkind: Secret\ndata:\n  token: {long_token}\n'

    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-secrets', 'content': content},
    ]}})
    extracted = _extract_content(rendered, 'k0s_manifest_my-secrets')

    assert f'token: {long_token}' in extracted


def test_content_multiple_base64_values_all_preserved():
    token1 = 'Zmlyc3RzZWNyZXQ='
    token2 = 'c2Vjb25kc2VjcmV0'
    content = (
        'apiVersion: v1\n'
        'kind: Secret\n'
        'data:\n'
        f'  first: {token1}\n'
        f'  second: {token2}\n'
    )

    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-secrets', 'content': content},
    ]}})
    extracted = _extract_content(rendered, 'k0s_manifest_my-secrets')

    assert f'first: {token1}' in extracted
    assert f'second: {token2}' in extracted


def test_content_internal_yaml_structure_is_parseable_by_kubectl():
    """Content must survive rendering with valid internal YAML structure intact."""
    b64_value = 'dmFsdWU='
    content = (
        'apiVersion: v1\n'
        'kind: Secret\n'
        'metadata:\n'
        '  name: my-secret\n'
        '  namespace: production\n'
        'data:\n'
        f'  token: {b64_value}\n'
    )

    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-secrets', 'content': content},
    ]}})
    extracted = _extract_content(rendered, 'k0s_manifest_my-secrets')

    # Parse the content as YAML exactly as kubectl would — structure must be intact
    parsed = yaml.safe_load(extracted)
    assert parsed['apiVersion'] == 'v1'
    assert parsed['kind'] == 'Secret'
    assert parsed['metadata']['name'] == 'my-secret'
    assert parsed['metadata']['namespace'] == 'production'
    assert parsed['data']['token'] == b64_value
