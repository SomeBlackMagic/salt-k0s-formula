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