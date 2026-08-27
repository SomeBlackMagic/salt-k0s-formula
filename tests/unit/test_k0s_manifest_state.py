import importlib.util


MODULE_PATH = 'k0s/_states/k0s_manifest.py'

NGINX_DEPLOYMENT = '''\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx:latest
'''

NGINX_SERVICE = '''\
apiVersion: v1
kind: Service
metadata:
  name: nginx
spec:
  selector:
    app: nginx
  ports:
    - port: 80
'''


def _load_state_module():
    spec = importlib.util.spec_from_file_location('k0s_manifest', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__opts__ = {'test': False}
    module.__salt__ = {}
    return module


def _create_binary(tmp_path):
    binary = tmp_path / 'k0s'
    binary.write_text('#!/bin/sh\n')
    binary.chmod(0o755)
    return binary


def _create_source(tmp_path, content=NGINX_DEPLOYMENT):
    source = tmp_path / 'manifest.yaml'
    source.write_text(content)
    return source


# --- validation ---


def test_applied_fails_when_neither_source_nor_content_given(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary))

    assert result['result'] is False
    assert 'source or content' in result['comment']


def test_applied_fails_when_content_is_not_a_string(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=42)

    assert result['result'] is False
    assert 'content must be a string' in result['comment']


def test_applied_fails_when_content_is_empty_string(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content='')

    assert result['result'] is False
    assert 'content must not be empty' in result['comment']


def test_applied_fails_when_content_is_whitespace_only(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content='   \n  ')

    assert result['result'] is False
    assert 'content must not be empty' in result['comment']


def test_applied_fails_when_content_is_only_a_separator(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content='---')

    assert result['result'] is False
    assert 'content must not be empty' in result['comment']


def test_applied_fails_when_binary_is_missing(tmp_path):
    state = _load_state_module()

    result = state.applied('test', binary='/nonexistent/k0s', content=NGINX_DEPLOYMENT)

    assert result['result'] is False
    assert '/nonexistent/k0s' in result['comment']


def test_applied_fails_when_source_file_is_missing(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), source='/nonexistent/manifest.yaml')

    assert result['result'] is False
    assert '/nonexistent/manifest.yaml' in result['comment']


def test_applied_uses_content_when_source_file_is_missing(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied(
        'test',
        binary=str(binary),
        source='/nonexistent/manifest.yaml',
        content=NGINX_DEPLOYMENT,
    )

    assert result['result'] is True
    assert calls[0]['stdin'] == NGINX_DEPLOYMENT


# --- test mode ---


def test_applied_reports_pending_change_in_test_mode_with_content(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is None
    assert result['changes'] == {}
    assert 'would be applied' in result['comment']
    assert calls == []


def test_applied_reports_pending_change_in_test_mode_with_source(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path)
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.applied('test', binary=str(binary), source=str(source))

    assert result['result'] is None
    assert result['changes'] == {}
    assert 'would be applied' in result['comment']
    assert calls == []


# --- successful apply ---


def test_applied_with_inline_content_sends_correct_command(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is True
    assert calls[0]['command'] == [str(binary), 'kubectl', 'apply', '-f', '-']
    assert calls[0]['stdin'] == NGINX_DEPLOYMENT


def test_applied_with_source_file_reads_and_sends_content(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, NGINX_DEPLOYMENT)
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), source=str(source))

    assert result['result'] is True
    assert calls[0]['stdin'] == NGINX_DEPLOYMENT


def test_applied_with_source_and_content_concatenates_both(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, NGINX_DEPLOYMENT)
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'command': command, 'stdin': stdin})
        return {
            'retcode': 0,
            'stdout': 'deployment.apps/nginx created\nservice/nginx created\n',
            'stderr': '',
        }

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), source=str(source), content=NGINX_SERVICE)

    assert result['result'] is True
    assert NGINX_DEPLOYMENT in calls[0]['stdin']
    assert NGINX_SERVICE in calls[0]['stdin']
    assert '---' in calls[0]['stdin']


# --- change detection ---


def test_applied_reports_created_resources_in_changes(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    def run_all(command, python_shell, stdin):
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx created\nservice/nginx created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is True
    assert 'deployment.apps/nginx' in result['changes']['manifests']['created']
    assert 'service/nginx' in result['changes']['manifests']['created']


def test_applied_reports_configured_resources_in_changes(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    def run_all(command, python_shell, stdin):
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx configured\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is True
    assert 'deployment.apps/nginx' in result['changes']['manifests']['configured']


def test_applied_reports_server_side_applied_resources_in_changes(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    def run_all(command, python_shell, stdin):
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx serverside-applied\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is True
    assert 'deployment.apps/nginx' in result['changes']['manifests']['serverside-applied']


def test_applied_reports_no_changes_when_all_unchanged(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    def run_all(command, python_shell, stdin):
        return {'retcode': 0, 'stdout': 'deployment.apps/nginx unchanged\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is True
    assert result['changes'] == {}
    assert 'up to date' in result['comment']


# --- separator deduplication ---


def test_applied_does_not_strip_trailing_separator_from_single_part(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    content_with_separator = NGINX_DEPLOYMENT + '\n---'
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=content_with_separator)

    assert result['result'] is True
    assert calls[0]['stdin'] == content_with_separator


def test_applied_strips_trailing_separator_from_source_before_concatenation(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, NGINX_DEPLOYMENT + '\n---')
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), source=str(source), content=NGINX_SERVICE)

    assert result['result'] is True
    stdin = calls[0]['stdin']
    assert '---\n---' not in stdin


def test_applied_strips_trailing_separator_from_content_before_concatenation(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, NGINX_DEPLOYMENT)
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), source=str(source), content=NGINX_SERVICE + '\n---')

    assert result['result'] is True
    stdin = calls[0]['stdin']
    assert '---\n---' not in stdin


# --- failure ---


def test_applied_handles_none_stdout_without_error(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    def run_all(command, python_shell, stdin):
        return {'retcode': 0, 'stdout': None, 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is True
    assert result['changes'] == {}
    assert 'up to date' in result['comment']


def test_applied_fails_clearly_when_kubectl_returns_nonzero(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    def run_all(command, python_shell, stdin):
        return {'retcode': 1, 'stdout': '', 'stderr': 'error: invalid manifest'}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT)

    assert result['result'] is False
    assert 'k0s kubectl apply failed' in result['comment']
    assert 'invalid manifest' in result['comment']


# --- wait conditions ---


WAIT_CONDITION = {'for': 'condition=Established', 'resource': 'crd/myresources.example.com'}


def test_applied_fails_when_wait_is_not_a_list(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT, wait='bad')

    assert result['result'] is False
    assert 'wait must be a list' in result['comment']


def test_applied_fails_when_wait_item_is_not_a_dict(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT, wait=['bad'])

    assert result['result'] is False
    assert 'wait[0] must be a dict' in result['comment']


def test_applied_fails_when_wait_item_missing_for(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'resource': 'crd/foo'}])

    assert result['result'] is False
    assert 'missing required key "for"' in result['comment']


def test_applied_fails_when_wait_item_missing_resource(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'for': 'condition=Established'}])

    assert result['result'] is False
    assert 'missing required key "resource"' in result['comment']


def test_applied_runs_wait_before_apply(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': 'crd/myresources.example.com created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[WAIT_CONDITION])

    assert result['result'] is True
    assert len(calls) == 2
    wait_cmd = calls[0]['command']
    assert wait_cmd[1] == 'kubectl'
    assert wait_cmd[2] == 'wait'
    assert '--for=condition=Established' in wait_cmd
    assert 'crd/myresources.example.com' in wait_cmd
    assert calls[1]['stdin'] == NGINX_DEPLOYMENT


def test_applied_wait_includes_timeout_when_specified(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append(command)
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    condition = {'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'}
    state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT, wait=[condition])

    assert '--timeout=60s' in calls[0]


def test_applied_wait_includes_namespace_when_specified(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append(command)
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    condition = {'for': 'condition=Ready', 'resource': 'deployment/app', 'namespace': 'prod'}
    state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT, wait=[condition])

    assert '-n' in calls[0]
    assert 'prod' in calls[0]


def test_applied_fails_when_wait_command_fails(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 1, 'stdout': '', 'stderr': 'timed out waiting for the condition'}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[WAIT_CONDITION])

    assert result['result'] is False
    assert 'k0s kubectl wait failed' in result['comment']
    assert 'timed out' in result['comment']
    # apply must not run when wait fails
    assert all(c['stdin'] is None for c in calls)


def test_applied_wait_reported_in_test_mode(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__opts__ = {'test': True}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[WAIT_CONDITION])

    assert result['result'] is None
    assert 'would be applied' in result['comment']
    assert 'Would wait first' in result['comment']
    assert calls == []


def test_applied_fails_when_wait_item_has_unknown_key(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'for': 'condition=Established', 'resource': 'crd/foo', 'timout': '60s'}])

    assert result['result'] is False
    assert 'unknown key' in result['comment']
    assert 'timout' in result['comment']


def test_applied_fails_when_wait_for_is_empty_string(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'for': '', 'resource': 'crd/foo'}])

    assert result['result'] is False
    assert 'must not be empty' in result['comment']
    assert '"for"' in result['comment']


def test_applied_fails_when_wait_resource_is_empty_string(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'for': 'condition=Established', 'resource': ''}])

    assert result['result'] is False
    assert 'must not be empty' in result['comment']
    assert '"resource"' in result['comment']


def test_applied_fails_when_wait_for_is_not_a_string(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'for': None, 'resource': 'crd/foo'}])

    assert result['result'] is False
    assert 'must be a string' in result['comment']
    assert '"for"' in result['comment']


def test_applied_fails_when_wait_resource_is_not_a_string(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[{'for': 'condition=Established', 'resource': 42}])

    assert result['result'] is False
    assert 'must be a string' in result['comment']
    assert '"resource"' in result['comment']


def test_applied_runs_wait_even_when_no_changes(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': 'crd/foo unchanged\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                           wait=[WAIT_CONDITION])

    assert result['result'] is True
    assert result['changes'] == {}
    assert len(calls) == 2  # wait + apply
    assert 'wait' in calls[0]['command']
    assert calls[1]['stdin'] == NGINX_DEPLOYMENT


def test_applied_stops_at_first_failed_wait_condition(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        if 'crd/bar' in command:
            return {'retcode': 1, 'stdout': '', 'stderr': 'timed out waiting for the condition'}
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    conditions = [
        {'for': 'condition=Established', 'resource': 'crd/foo'},
        {'for': 'condition=Established', 'resource': 'crd/bar'},
    ]
    result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT, wait=conditions)

    assert result['result'] is False
    assert 'timed out' in result['comment']
    # apply must not run when a wait condition fails
    assert all(c['stdin'] is None for c in calls)


def test_applied_runs_multiple_wait_conditions_in_order(tmp_path):
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    conditions = [
        {'for': 'condition=Established', 'resource': 'crd/foo'},
        {'for': 'condition=Established', 'resource': 'crd/bar'},
    ]
    state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT, wait=conditions)

    assert len(calls) == 3  # 2 wait + 1 apply
    assert 'crd/foo' in calls[0]['command']
    assert 'crd/bar' in calls[1]['command']
    assert calls[2]['stdin'] == NGINX_DEPLOYMENT


# --- source + wait: pre-condition before apply ---

SECRET_STORE_MANIFEST = '''\
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: infra
spec:
  provider: {}
'''

CRD_WAIT_CONDITION = {
    'for': 'condition=Established',
    'resource': 'crd/clustersecretstores.external-secrets.io',
    'timeout': '60s',
}


def test_applied_with_source_and_wait_runs_wait_before_apply(tmp_path):
    """source + wait: wait must run before kubectl apply."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, SECRET_STORE_MANIFEST)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': 'clustersecretstore.external-secrets.io/infra created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied(
        'test',
        binary=str(binary),
        source=str(source),
        wait=[CRD_WAIT_CONDITION],
    )

    assert result['result'] is True
    assert len(calls) == 2
    assert 'wait' in calls[0]['command']
    assert calls[0]['stdin'] is None
    assert calls[1]['stdin'] == SECRET_STORE_MANIFEST


def test_applied_with_source_and_wait_does_not_apply_when_wait_fails(tmp_path):
    """source + wait: apply must not run if wait fails."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, SECRET_STORE_MANIFEST)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 1, 'stdout': '', 'stderr': 'timed out waiting for the condition'}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied(
        'test',
        binary=str(binary),
        source=str(source),
        wait=[CRD_WAIT_CONDITION],
    )

    assert result['result'] is False
    assert 'k0s kubectl wait failed' in result['comment']
    assert 'timed out' in result['comment']
    assert all(c['stdin'] is None for c in calls)


def test_applied_with_source_and_content_without_wait_concatenates(tmp_path):
    """Without wait, source+content must be applied in a single kubectl call."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, NGINX_DEPLOYMENT)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied(
        'test',
        binary=str(binary),
        source=str(source),
        content=NGINX_SERVICE,
    )

    assert result['result'] is True
    assert len(calls) == 1
    assert NGINX_DEPLOYMENT in calls[0]['stdin']
    assert NGINX_SERVICE in calls[0]['stdin']


def test_applied_with_source_content_and_wait_runs_wait_then_single_apply(tmp_path):
    """source + content + wait: wait runs first, then single concatenated apply."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    source = _create_source(tmp_path, NGINX_DEPLOYMENT)
    calls = []

    def run_all(command, python_shell, stdin=None):
        calls.append({'command': command, 'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    result = state.applied(
        'test',
        binary=str(binary),
        source=str(source),
        content=SECRET_STORE_MANIFEST,
        wait=[CRD_WAIT_CONDITION],
    )

    assert result['result'] is True
    assert len(calls) == 2
    assert 'wait' in calls[0]['command']
    assert calls[0]['stdin'] is None
    assert NGINX_DEPLOYMENT in calls[1]['stdin']
    assert SECRET_STORE_MANIFEST in calls[1]['stdin']


# --- template rendering ---


def test_applied_with_template_false_does_not_render_content(tmp_path):
    """When template=False (default), Jinja2 tags in content are passed as-is."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__pillar__ = {'key': 'value'}
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    content = 'apiVersion: v1\nkind: ConfigMap\ndata:\n  key: {{ pillar["key"] }}\n'
    result = state.applied('test', binary=str(binary), content=content, template=False)

    assert result['result'] is True
    assert '{{ pillar["key"] }}' in calls[0]['stdin']


def test_applied_with_template_true_renders_content_with_pillar(tmp_path):
    """When template=True, Jinja2 tags in content are rendered using __pillar__."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__pillar__ = {'db': {'host': 'postgres.svc'}}
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    content = 'apiVersion: v1\nkind: ConfigMap\ndata:\n  host: {{ pillar["db"]["host"] }}\n'
    result = state.applied('test', binary=str(binary), content=content, template=True)

    assert result['result'] is True
    assert 'postgres.svc' in calls[0]['stdin']
    assert '{{' not in calls[0]['stdin']


def test_applied_with_template_true_renders_content_with_grains(tmp_path):
    """When template=True, Jinja2 tags in content can access __grains__."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__grains__ = {'id': 'node-01'}
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    content = 'apiVersion: v1\nkind: ConfigMap\ndata:\n  node: {{ grains["id"] }}\n'
    result = state.applied('test', binary=str(binary), content=content, template=True)

    assert result['result'] is True
    assert 'node-01' in calls[0]['stdin']


def test_applied_with_template_true_renders_source_with_pillar(tmp_path):
    """When template=True, source file contents are rendered using __pillar__."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__pillar__ = {'app': {'replicas': '3'}}
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    source = _create_source(
        tmp_path,
        'apiVersion: apps/v1\nkind: Deployment\nspec:\n  replicas: {{ pillar["app"]["replicas"] }}\n',
    )
    result = state.applied('test', binary=str(binary), source=str(source), template=True)

    assert result['result'] is True
    assert 'replicas: 3' in calls[0]['stdin']
    assert '{{' not in calls[0]['stdin']


def test_applied_with_template_true_and_template_vars(tmp_path):
    """template_vars are available as top-level variables in the template."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__pillar__ = {}
    calls = []

    def run_all(command, python_shell, stdin):
        calls.append({'stdin': stdin})
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    content = 'apiVersion: v1\nkind: ConfigMap\ndata:\n  env: {{ environment }}\n'
    result = state.applied(
        'test',
        binary=str(binary),
        content=content,
        template=True,
        template_vars={'environment': 'production'},
    )

    assert result['result'] is True
    assert 'env: production' in calls[0]['stdin']


def test_applied_with_template_true_reports_render_error(tmp_path):
    """When template rendering fails, result=False is returned with a clear message."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__pillar__ = {}
    state.__salt__ = {}

    content = 'apiVersion: v1\nkind: ConfigMap\ndata:\n  key: {{ undefined_variable }}\n'
    result = state.applied('test', binary=str(binary), content=content, template=True)

    assert result['result'] is False
    assert 'template' in result['comment'].lower()


def test_applied_with_template_true_in_test_mode_does_not_apply(tmp_path):
    """In test mode with template=True, content is rendered but apply does not run."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    state.__opts__ = {'test': True}
    state.__pillar__ = {'zone': 'eu-west'}
    calls = []
    state.__salt__ = {'cmd.run_all': calls.append}

    content = 'apiVersion: v1\nkind: ConfigMap\ndata:\n  zone: {{ pillar["zone"] }}\n'
    result = state.applied('test', binary=str(binary), content=content, template=True)

    assert result['result'] is None
    assert calls == []
    assert 'would be applied' in result['comment']


# --- wait retry on NotFound ---


def test_wait_retries_when_resource_not_found(tmp_path):
    """wait must retry kubectl wait when the resource is not found yet."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    call_count = [0]
    slept = []

    def run_all(command, python_shell, stdin=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return {'retcode': 1, 'stdout': '', 'stderr': 'Error from server (NotFound): customresourcedefinitions.apiextensions.k8s.io "foo.example.com" not found'}
        return {'retcode': 0, 'stdout': '', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    condition = {'for': 'condition=Established', 'resource': 'crd/foo.example.com', 'timeout': '60s'}
    result = state._run_wait(str(binary), condition, _sleep=slept.append)

    assert result['retcode'] == 0
    assert call_count[0] == 2
    assert slept == [2]


def test_wait_stops_retrying_after_deadline(tmp_path):
    """wait must stop retrying and report failure when deadline is exceeded."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    calls = []
    slept = []
    not_found_response = {'retcode': 1, 'stdout': '', 'stderr': 'Error from server (NotFound): not found'}

    def run_all(command, python_shell, stdin=None):
        calls.append(command)
        return not_found_response

    state.__salt__ = {'cmd.run_all': run_all}

    # 1s timeout so deadline passes quickly; _sleep is mocked but time.time() advances
    condition = {'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '1s'}

    import time as real_time
    tick = [real_time.time()]

    def fake_sleep(s):
        slept.append(s)
        # advance simulated time past deadline on first sleep
        tick[0] += 10

    original_time = state.time if hasattr(state, 'time') else None

    import unittest.mock as mock
    with mock.patch('time.time', side_effect=lambda: tick[0]):
        result = state._run_wait(str(binary), condition, _sleep=fake_sleep)

    assert result['retcode'] == 1
    assert 'not found' in result['stderr']


def test_wait_does_not_retry_on_non_notfound_error(tmp_path):
    """wait must not retry on errors that are not NotFound."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    call_count = [0]
    slept = []

    def run_all(command, python_shell, stdin=None):
        call_count[0] += 1
        return {'retcode': 1, 'stdout': '', 'stderr': 'timed out waiting for the condition'}

    state.__salt__ = {'cmd.run_all': run_all}

    condition = {'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'}
    result = state._run_wait(str(binary), condition, _sleep=slept.append)

    assert result['retcode'] == 1
    assert call_count[0] == 1
    assert slept == []


def test_applied_retries_wait_when_resource_not_found(tmp_path):
    """applied() must retry wait transparently when resource is not found."""
    state = _load_state_module()
    binary = _create_binary(tmp_path)
    call_count = [0]

    def run_all(command, python_shell, stdin=None):
        call_count[0] += 1
        if 'wait' in command and call_count[0] == 1:
            return {'retcode': 1, 'stdout': '', 'stderr': 'Error from server (NotFound): not found'}
        return {'retcode': 0, 'stdout': 'crd/foo created\n', 'stderr': ''}

    state.__salt__ = {'cmd.run_all': run_all}

    # patch _sleep inside _run_wait so test does not actually sleep
    import unittest.mock as mock
    condition = {'for': 'condition=Established', 'resource': 'crd/foo', 'timeout': '60s'}
    with mock.patch('time.sleep'):
        result = state.applied('test', binary=str(binary), content=NGINX_DEPLOYMENT,
                               wait=[condition])

    assert result['result'] is True
