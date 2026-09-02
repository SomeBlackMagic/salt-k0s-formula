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


def _params(rendered, state_id):
    block = _state_block(rendered, state_id)
    return {k: v for item in block['k0s_manifest.applied'] for k, v in item.items()}


# ---------------------------------------------------------------------------
# Empty / no manifests
# ---------------------------------------------------------------------------


def test_no_manifests_renders_empty():
    rendered = _render({'k0s': {}})

    assert yaml.safe_load(rendered) is None


def test_empty_list_renders_empty():
    rendered = _render({'k0s': {'manifests': []}})

    assert yaml.safe_load(rendered) is None


def test_empty_map_renders_empty():
    rendered = _render({'k0s': {'manifests_extra': {}}})

    assert yaml.safe_load(rendered) is None


def test_empty_list_and_empty_map_render_empty():
    rendered = _render({'k0s': {'manifests': [], 'manifests_extra': {}}})

    assert yaml.safe_load(rendered) is None


# ---------------------------------------------------------------------------
# List format (manifests)
# ---------------------------------------------------------------------------


def test_list_single_manifest_produces_state_id_from_name():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    assert 'k0s_manifest_my-crds' in _state_ids(rendered)


def test_list_manifest_name_appears_in_state_name_field():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    assert _params(rendered, 'k0s_manifest_my-crds')['name'] == 'my-crds'


def test_list_multiple_manifests_produce_distinct_state_ids():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
        {'name': 'connectors', 'source': '/srv/salt/connectors.yaml'},
    ]}})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_crds' in ids
    assert 'k0s_manifest_connectors' in ids


def test_list_manifest_source_is_passed_through():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    assert _params(rendered, 'k0s_manifest_crds')['source'] == '/srv/salt/crds.yaml'


def test_list_manifest_wait_is_passed_through():
    rendered = _render({'k0s': {'manifests': [
        {
            'name': 'crds',
            'source': '/srv/salt/crds.yaml',
            'wait': [{'for': 'condition=Established', 'resource': 'crd/foo'}],
        },
    ]}})

    assert _params(rendered, 'k0s_manifest_crds')['wait'] == [
        {'for': 'condition=Established', 'resource': 'crd/foo'},
    ]


def test_list_manifest_without_source_omits_source_param():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'inline', 'content': 'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: test\n'},
    ]}})

    assert 'source' not in _params(rendered, 'k0s_manifest_inline')


# ---------------------------------------------------------------------------
# Map format (manifests_extra)
# ---------------------------------------------------------------------------


def test_map_key_becomes_state_id():
    rendered = _render({'k0s': {'manifests_extra': {
        'my-crds': {'source': '/srv/salt/crds.yaml'},
    }}})

    assert 'k0s_manifest_my-crds' in _state_ids(rendered)


def test_map_key_becomes_name_field():
    rendered = _render({'k0s': {'manifests_extra': {
        'my-crds': {'source': '/srv/salt/crds.yaml'},
    }}})

    assert _params(rendered, 'k0s_manifest_my-crds')['name'] == 'my-crds'


def test_map_multiple_keys_produce_distinct_state_ids():
    rendered = _render({'k0s': {'manifests_extra': {
        'crds': {'source': '/srv/salt/crds.yaml'},
        'connectors': {'source': '/srv/salt/connectors.yaml'},
    }}})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_crds' in ids
    assert 'k0s_manifest_connectors' in ids


def test_map_source_is_passed_through():
    rendered = _render({'k0s': {'manifests_extra': {
        'crds': {'source': '/srv/salt/crds.yaml'},
    }}})

    assert _params(rendered, 'k0s_manifest_crds')['source'] == '/srv/salt/crds.yaml'


def test_map_wait_is_passed_through():
    rendered = _render({'k0s': {'manifests_extra': {
        'crds': {
            'source': '/srv/salt/crds.yaml',
            'wait': [{'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'}],
        },
    }}})

    assert _params(rendered, 'k0s_manifest_crds')['wait'] == [
        {'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'},
    ]


def test_map_content_source_and_wait_all_passed_through():
    rendered = _render({'k0s': {'manifests_extra': {
        'external-secrets-connectors': {
            'source': '/etc/k0s/external-secrets-connectors.yaml',
            'content': 'apiVersion: external-secrets.io/v1\nkind: ClusterSecretStore\n',
            'wait': [{'for': 'condition=Established',
                      'resource': 'crd/clustersecretstores.external-secrets.io',
                      'timeout': '60s'}],
        },
    }}})

    params = _params(rendered, 'k0s_manifest_external-secrets-connectors')
    assert params['name'] == 'external-secrets-connectors'
    assert params['source'] == '/etc/k0s/external-secrets-connectors.yaml'
    assert 'ClusterSecretStore' in params['content']
    assert params['wait'][0]['resource'] == 'crd/clustersecretstores.external-secrets.io'


# ---------------------------------------------------------------------------
# Combined: list + map merge
# ---------------------------------------------------------------------------


def test_map_matching_name_merges_into_list_entry():
    """Map entry whose key matches a list entry name is merged into that entry."""
    rendered = _render({'k0s': {
        'manifests': [
            {'name': 'nginx', 'source': '/srv/salt/nginx.yaml'},
        ],
        'manifests_extra': {
            'nginx': {'wait': [{'for': 'condition=Available', 'resource': 'deployment/nginx'}]},
        },
    }})

    params = _params(rendered, 'k0s_manifest_nginx')
    assert params['source'] == '/srv/salt/nginx.yaml'
    assert params['wait'] == [{'for': 'condition=Available', 'resource': 'deployment/nginx'}]


def test_map_overrides_existing_field_on_conflict():
    """When a key exists in both list entry and map entry, map value wins."""
    rendered = _render({'k0s': {
        'manifests': [
            {'name': 'app', 'source': '/srv/salt/old.yaml'},
        ],
        'manifests_extra': {
            'app': {'source': '/srv/salt/new.yaml'},
        },
    }})

    assert _params(rendered, 'k0s_manifest_app')['source'] == '/srv/salt/new.yaml'


def test_map_unmatched_key_appended_as_new_entry():
    """Map entry whose key has no match in the list is appended as a new manifest."""
    rendered = _render({'k0s': {
        'manifests': [
            {'name': 'base', 'source': '/srv/salt/base.yaml'},
        ],
        'manifests_extra': {
            'extra': {'source': '/srv/salt/extra.yaml'},
        },
    }})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_base' in ids
    assert 'k0s_manifest_extra' in ids


def test_map_appended_entry_has_correct_name_field():
    rendered = _render({'k0s': {
        'manifests': [],
        'manifests_extra': {
            'extra': {'source': '/srv/salt/extra.yaml'},
        },
    }})

    assert _params(rendered, 'k0s_manifest_extra')['name'] == 'extra'


def test_map_does_not_mutate_unrelated_list_entries():
    """Merging one entry must not affect other entries in the list."""
    rendered = _render({'k0s': {
        'manifests': [
            {'name': 'a', 'source': '/srv/salt/a.yaml'},
            {'name': 'b', 'source': '/srv/salt/b.yaml'},
        ],
        'manifests_extra': {
            'a': {'wait': [{'for': 'condition=Available', 'resource': 'deployment/a'}]},
        },
    }})

    params_b = _params(rendered, 'k0s_manifest_b')
    assert params_b['source'] == '/srv/salt/b.yaml'
    assert 'wait' not in params_b


def test_mixed_some_match_some_append():
    """Partial overlap: matched entries are merged, unmatched are appended."""
    rendered = _render({'k0s': {
        'manifests': [
            {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
            {'name': 'app', 'source': '/srv/salt/app.yaml'},
        ],
        'manifests_extra': {
            'crds': {'wait': [{'for': 'condition=Established', 'resource': 'crd/foo'}]},
            'monitoring': {'source': '/srv/salt/monitoring.yaml'},
        },
    }})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_crds' in ids
    assert 'k0s_manifest_app' in ids
    assert 'k0s_manifest_monitoring' in ids

    assert _params(rendered, 'k0s_manifest_crds')['source'] == '/srv/salt/crds.yaml'
    assert _params(rendered, 'k0s_manifest_crds')['wait'] == [
        {'for': 'condition=Established', 'resource': 'crd/foo'},
    ]
    assert _params(rendered, 'k0s_manifest_monitoring')['source'] == '/srv/salt/monitoring.yaml'


def test_map_only_no_list_produces_states():
    """manifests_extra alone (no manifests list) still produces all states."""
    rendered = _render({'k0s': {
        'manifests_extra': {
            'crds': {'source': '/srv/salt/crds.yaml'},
            'app': {'source': '/srv/salt/app.yaml'},
        },
    }})

    ids = _state_ids(rendered)
    assert 'k0s_manifest_crds' in ids
    assert 'k0s_manifest_app' in ids


def test_list_only_no_map_produces_states():
    """manifests list alone (no manifests_extra) still produces all states."""
    rendered = _render({'k0s': {
        'manifests': [
            {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
        ],
    }})

    assert 'k0s_manifest_crds' in _state_ids(rendered)


# ---------------------------------------------------------------------------
# Binary
# ---------------------------------------------------------------------------


def test_default_binary_is_used_when_not_in_pillar():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'crds', 'source': '/srv/salt/crds.yaml'},
    ]}})

    assert _params(rendered, 'k0s_manifest_crds')['binary'] == DEFAULT_BINARY


def test_custom_binary_from_pillar_is_used():
    rendered = _render({'k0s': {
        'binary': '/opt/k0s/bin/k0s',
        'manifests': [{'name': 'crds', 'source': '/srv/salt/crds.yaml'}],
    }})

    assert _params(rendered, 'k0s_manifest_crds')['binary'] == '/opt/k0s/bin/k0s'


# ---------------------------------------------------------------------------
# Base64 content integrity
#
# Guard against template rendering corrupting base64 values in Secrets.
# The `indent` filter must not split or modify values on long lines.
# ---------------------------------------------------------------------------


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
    return _params(rendered, state_id)['content']


def test_content_base64_value_preserved_in_list_format():
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-secrets', 'content': _SECRET_CONTENT},
    ]}})

    assert f'token: {_B64_TOKEN}' in _extract_content(rendered, 'k0s_manifest_my-secrets')


def test_content_base64_value_preserved_in_map_format():
    rendered = _render({'k0s': {'manifests_extra': {
        'my-secrets': {'content': _SECRET_CONTENT},
    }}})

    assert f'token: {_B64_TOKEN}' in _extract_content(rendered, 'k0s_manifest_my-secrets')


def test_content_base64_value_preserved_after_map_merge():
    """Base64 content added via map merge must survive rendering intact."""
    rendered = _render({'k0s': {
        'manifests': [{'name': 'my-secrets', 'source': '/srv/salt/secrets.yaml'}],
        'manifests_extra': {'my-secrets': {'content': _SECRET_CONTENT}},
    }})

    assert f'token: {_B64_TOKEN}' in _extract_content(rendered, 'k0s_manifest_my-secrets')


def test_content_long_base64_value_is_not_line_wrapped():
    """Long values (e.g. k8s service account tokens) must not be split across lines."""
    long_token = 'eyJhbGciOiJSUzI1NiIsImtpZCI6IiJ9.' + 'A' * 200 + '.signature'
    content = f'apiVersion: v1\nkind: Secret\ndata:\n  token: {long_token}\n'

    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-secrets', 'content': content},
    ]}})

    assert f'token: {long_token}' in _extract_content(rendered, 'k0s_manifest_my-secrets')


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

    parsed = yaml.safe_load(extracted)
    assert parsed['apiVersion'] == 'v1'
    assert parsed['kind'] == 'Secret'
    assert parsed['metadata']['name'] == 'my-secret'
    assert parsed['metadata']['namespace'] == 'production'
    assert parsed['data']['token'] == b64_value


# ---------------------------------------------------------------------------
# Template parameter passthrough
# ---------------------------------------------------------------------------


def test_list_manifest_template_true_is_passed_through():
    """template: true from list entry must appear in the rendered state."""
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-cm', 'content': 'apiVersion: v1\nkind: ConfigMap\n', 'template': True},
    ]}})

    assert _params(rendered, 'k0s_manifest_my-cm')['template'] is True


def test_list_manifest_without_template_omits_template_param():
    """When template is not set in a list entry, it must be absent from the state."""
    rendered = _render({'k0s': {'manifests': [
        {'name': 'my-cm', 'content': 'apiVersion: v1\nkind: ConfigMap\n'},
    ]}})

    assert 'template' not in _params(rendered, 'k0s_manifest_my-cm')


def test_list_manifest_template_vars_are_passed_through():
    """template_vars from a list entry must be passed to the rendered state."""
    rendered = _render({'k0s': {'manifests': [
        {
            'name': 'my-cm',
            'content': 'apiVersion: v1\nkind: ConfigMap\n',
            'template': True,
            'template_vars': {'env': 'production'},
        },
    ]}})

    params = _params(rendered, 'k0s_manifest_my-cm')
    assert params['template_vars'] == {'env': 'production'}


def test_map_manifest_template_true_is_passed_through():
    """template: true from a map entry must appear in the rendered state."""
    rendered = _render({'k0s': {'manifests_extra': {
        'my-cm': {'content': 'apiVersion: v1\nkind: ConfigMap\n', 'template': True},
    }}})

    assert _params(rendered, 'k0s_manifest_my-cm')['template'] is True


def test_map_manifest_without_template_omits_template_param():
    """When template is not set in a map entry, it must be absent from the state."""
    rendered = _render({'k0s': {'manifests_extra': {
        'my-cm': {'content': 'apiVersion: v1\nkind: ConfigMap\n'},
    }}})

    assert 'template' not in _params(rendered, 'k0s_manifest_my-cm')


def test_map_manifest_template_vars_are_passed_through():
    """template_vars from a map entry must be passed to the rendered state."""
    rendered = _render({'k0s': {'manifests_extra': {
        'my-cm': {
            'content': 'apiVersion: v1\nkind: ConfigMap\n',
            'template': True,
            'template_vars': {'zone': 'eu-west'},
        },
    }}})

    params = _params(rendered, 'k0s_manifest_my-cm')
    assert params['template_vars'] == {'zone': 'eu-west'}