import os
import re
import time


__virtualname__ = 'k0s_manifest'

DEFAULT_BINARY = '/usr/local/bin/k0s'


def __virtual__():
    return __virtualname__


def applied(name, binary=DEFAULT_BINARY, source=None, content=None, wait=None):
    '''
    Apply Kubernetes manifests via k0s kubectl apply.

    At least one of source or content must be provided. Both may be given
    simultaneously — their YAML documents are concatenated before applying.

    name
        Arbitrary identifier used as the state name.

    binary
        Path to the k0s binary. Defaults to /usr/local/bin/k0s.

    source
        Path to a manifest file on the local filesystem.

    content
        Inline YAML manifest string.

    wait
        Optional list of pre-conditions that must be satisfied before any
        manifest is applied. All conditions are checked in order before
        kubectl apply runs. Each item is a dict with the following keys:

        for (required)
            The condition expression passed to --for, e.g.
            ``condition=Established`` or ``condition=Ready``.

        resource (required)
            The resource reference, e.g. ``crd/myresources.example.com`` or
            ``deployment/my-app``.

        timeout (optional)
            Timeout duration string passed to --timeout, e.g. ``60s`` or
            ``2m``. If omitted, kubectl uses its own default (30s).

        namespace (optional)
            Namespace passed to -n. Required for namespace-scoped resources.

    Example pillar::

        k0s:
          manifests:
            - name: my-crds
              source: /srv/salt/files/crds.yaml
              wait:
                - for: condition=Established
                  resource: crd/myresources.example.com
                  timeout: 60s
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
    }

    if source is None and content is None:
        ret['result'] = False
        ret['comment'] = 'At least one of source or content must be provided.'
        return ret

    if wait is not None:
        wait_error = _validate_wait(wait)
        if wait_error:
            ret['result'] = False
            ret['comment'] = wait_error
            return ret

    if content is not None and not isinstance(content, str):
        ret['result'] = False
        ret['comment'] = 'content must be a string.'
        return ret

    if content is not None and not _strip_trailing_separator(content).strip():
        ret['result'] = False
        ret['comment'] = 'content must not be empty.'
        return ret

    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        ret['result'] = False
        ret['comment'] = 'Missing required file: {0}.'.format(binary)
        return ret

    source_content = None
    if source is not None:
        source_result = _read_source(source)
        if not source_result['result']:
            if content is None:
                ret['result'] = False
                ret['comment'] = source_result['comment']
                return ret
        else:
            source_content = source_result['content']

    command = [binary, 'kubectl', 'apply', '-f', '-']

    parts = []
    if source_content is not None:
        parts.append(source_content)
    if content is not None:
        parts.append(content)
    if len(parts) == 1:
        manifest = parts[0]
    else:
        manifest = '\n---\n'.join(_strip_trailing_separator(p) for p in parts)

    if __opts__.get('test'):
        ret['result'] = None
        comment = 'Manifests would be applied with: {0}'.format(' '.join(command))
        if wait:
            wait_commands = [' '.join(_build_wait_command(binary, c)) for c in wait]
            comment += '\nWould wait first: {0}'.format('; '.join(wait_commands))
        ret['comment'] = comment
        return ret

    # Run wait conditions as pre-conditions before any apply.
    if wait:
        for condition in wait:
            wait_result = _run_wait(binary, condition)
            if wait_result.get('retcode') != 0:
                ret['result'] = False
                ret['comment'] = _wait_failure_comment(wait_result, condition)
                return ret

    result = __salt__['cmd.run_all'](
        command,
        python_shell=False,
        stdin=manifest,
    )

    if result.get('retcode') != 0:
        ret['result'] = False
        ret['comment'] = _command_failure_comment(result)
        return ret

    stdout = result.get('stdout') or ''
    changes = _parse_changes(stdout)
    if changes:
        ret['changes'] = {'manifests': changes}
        ret['comment'] = 'Manifests were applied.'
    else:
        ret['comment'] = 'Manifests are already up to date.'

    return ret


_WAIT_KNOWN_KEYS = {'for', 'resource', 'timeout', 'namespace'}
_WAIT_STRING_KEYS = ('for', 'resource', 'timeout', 'namespace')


def _validate_wait(wait):
    if not isinstance(wait, list):
        return 'wait must be a list.'
    for i, condition in enumerate(wait):
        if not isinstance(condition, dict):
            return 'wait[{0}] must be a dict.'.format(i)
        unknown = set(condition) - _WAIT_KNOWN_KEYS
        if unknown:
            return 'wait[{0}] contains unknown key(s): {1}.'.format(
                i, ', '.join(sorted(unknown))
            )
        if 'for' not in condition:
            return 'wait[{0}] is missing required key "for".'.format(i)
        if 'resource' not in condition:
            return 'wait[{0}] is missing required key "resource".'.format(i)
        for key in _WAIT_STRING_KEYS:
            if key in condition and not isinstance(condition[key], str):
                return 'wait[{0}]["{1}"] must be a string.'.format(i, key)
        if not condition['for'].strip():
            return 'wait[{0}]["for"] must not be empty.'.format(i)
        if not condition['resource'].strip():
            return 'wait[{0}]["resource"] must not be empty.'.format(i)
    return None


def _build_wait_command(binary, condition):
    command = [binary, 'kubectl', 'wait',
               '--for={0}'.format(condition['for']),
               condition['resource']]
    if 'namespace' in condition:
        command.extend(['-n', condition['namespace']])
    if 'timeout' in condition:
        command.append('--timeout={0}'.format(condition['timeout']))
    return command


_WAIT_RETRY_INTERVAL = 2
_WAIT_NOT_FOUND_PHRASES = ('not found', 'notfound')


def _run_wait(binary, condition, _sleep=None):
    '''
    Run kubectl wait for a condition, retrying when the resource does not exist
    yet. ``kubectl wait`` fails immediately with NotFound if the resource has
    not been created yet (e.g. a CRD installed by a Helm chart that is still
    starting up). This wrapper retries until the timeout is exhausted.
    '''
    if _sleep is None:
        _sleep = time.sleep

    wait_command = _build_wait_command(binary, condition)
    timeout_seconds = _parse_timeout_seconds(condition.get('timeout', '30s'))
    deadline = time.time() + timeout_seconds

    while True:
        result = __salt__['cmd.run_all'](wait_command, python_shell=False)
        if result.get('retcode') == 0:
            return result
        output = (result.get('stderr') or result.get('stdout') or '').lower()
        if any(p in output for p in _WAIT_NOT_FOUND_PHRASES) and time.time() < deadline:
            _sleep(_WAIT_RETRY_INTERVAL)
            if time.time() >= deadline:
                return result
            continue
        return result


def _parse_timeout_seconds(timeout_str):
    '''Parse a kubectl timeout string (e.g. ``60s``, ``2m``, ``1h``) into seconds.'''
    match = re.match(r'^(\d+)(s|m|h)$', timeout_str.strip())
    if not match:
        return 30
    value, unit = int(match.group(1)), match.group(2)
    return value * {'s': 1, 'm': 60, 'h': 3600}[unit]


def _wait_failure_comment(result, condition):
    output = result.get('stderr') or result.get('stdout') or 'no output'
    return 'k0s kubectl wait failed for {0} (--for={1}) with exit code {2}: {3}'.format(
        condition['resource'],
        condition['for'],
        result.get('retcode'),
        output.strip(),
    )


def _read_source(source):
    if not os.path.isfile(source):
        return {
            'result': False,
            'comment': 'Source file not found: {0}.'.format(source),
        }

    try:
        with open(source, 'r') as manifest_file:
            return {'result': True, 'content': manifest_file.read()}
    except OSError as exc:
        return {
            'result': False,
            'comment': 'Unable to read source file {0}: {1}.'.format(source, exc),
        }


def _parse_changes(output):
    created = []
    configured = []
    server_side_applied = []

    for line in output.splitlines():
        line = line.strip()
        if line.endswith(' created'):
            created.append(line[: -len(' created')])
        elif line.endswith(' configured'):
            configured.append(line[: -len(' configured')])
        elif line.endswith(' serverside-applied'):
            server_side_applied.append(line[: -len(' serverside-applied')])

    changes = {}
    if created:
        changes['created'] = created
    if configured:
        changes['configured'] = configured
    if server_side_applied:
        changes['serverside-applied'] = server_side_applied

    return changes


def _strip_trailing_separator(content):
    '''Remove a trailing YAML document separator (---) from a manifest string.'''
    return re.sub(r'\s*---\s*\Z', '', content)


def _command_failure_comment(result):
    output = result.get('stderr') or result.get('stdout') or 'no output'
    return 'k0s kubectl apply failed with exit code {0}: {1}'.format(
        result.get('retcode'),
        output.strip(),
    )