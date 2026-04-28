# Stage 9 — Kitchen Suites and Testinfra Tests

## Goal

Cover all formula roles with integration tests. Each suite runs a full
`kitchen test --destroy=always` cycle: create → converge → verify → destroy.

## Deliverables

### 9.1 Suite overview

| Suite | Role | Pillar file | Tests |
|---|---|---|---|
| `default` | `single` | `tests/pillar/single.sls` | install, config, service, cluster health |
| `controller` | `controller` | `tests/pillar/controller.sls` | install, config, unit flags, service |
| `worker` | `worker` | `tests/pillar/worker.sls` | install, token file, unit flags, service |
| `custom-network` | `single` | `tests/pillar/custom-network.sls` | Calico provider in config |

### 9.2 `.kitchen.yml` additions

```yaml
suites:
  - name: default
    verifier:
      command: .venv/bin/pytest tests/integration/default/ -v --html=reports/report-default.html
    provisioner:
      pillars_from_files:
        base.sls: tests/pillar/single.sls
      state_top:
        base:
          "*":
            - k0s

  - name: controller
    verifier:
      command: .venv/bin/pytest tests/integration/controller/ -v --html=reports/report-controller.html
    provisioner:
      pillars_from_files:
        base.sls: tests/pillar/controller.sls
      state_top:
        base:
          "*":
            - k0s

  - name: worker
    verifier:
      command: .venv/bin/pytest tests/integration/worker/ -v --html=reports/report-worker.html
    provisioner:
      pillars_from_files:
        base.sls: tests/pillar/worker.sls
      state_top:
        base:
          "*":
            - k0s

  - name: custom-network
    verifier:
      command: .venv/bin/pytest tests/integration/custom-network/ -v --html=reports/report-custom-network.html
    provisioner:
      pillars_from_files:
        base.sls: tests/pillar/custom-network.sls
      state_top:
        base:
          "*":
            - k0s
```

### 9.3 Pillar files

**`tests/pillar/single.sls`**
```yaml
k0s:
  version: 'v1.30.2+k0s.0'
  role: single
  config:
    spec:
      telemetry:
        enabled: false
```

**`tests/pillar/controller.sls`**
```yaml
k0s:
  version: 'v1.30.2+k0s.0'
  role: controller
  controller:
    enable_worker: false
    no_taints: false
  config:
    spec:
      telemetry:
        enabled: false
```

**`tests/pillar/worker.sls`**
```yaml
k0s:
  version: 'v1.30.2+k0s.0'
  role: worker
  worker:
    join_token: 'dummy-token-for-testing'
    api_address: '127.0.0.1:6443'
```

**`tests/pillar/custom-network.sls`**
```yaml
k0s:
  version: 'v1.30.2+k0s.0'
  role: single
  config:
    spec:
      network:
        provider: calico
        podCIDR: 192.168.0.0/16
      telemetry:
        enabled: false
```

### 9.4 Test cases by suite

#### `default` and `controller` — binary and config

```python
def test_binary_exists(host):
    assert host.file('/usr/local/bin/k0s').exists

def test_binary_executable(host):
    assert host.file('/usr/local/bin/k0s').mode == 0o755

def test_binary_version(host, k0s_version):
    result = host.run('k0s version')
    assert result.rc == 0
    assert k0s_version in result.stdout

def test_config_exists(host):
    assert host.file('/etc/k0s/k0s.yaml').exists

def test_config_permissions(host):
    f = host.file('/etc/k0s/k0s.yaml')
    assert f.mode == 0o600
    assert f.user == 'root'

def test_config_valid(host):
    assert host.run('k0s config validate').rc == 0
```

#### `default` — service and cluster health (single role)

```python
def test_service_enabled(host):
    assert host.service('k0scontroller').is_enabled

def test_service_running(host):
    assert host.service('k0scontroller').is_running

def test_cluster_api_reachable(host):
    result = host.run('k0s kubectl get nodes')
    assert result.rc == 0

def test_node_ready(host):
    result = host.run(
        "k0s kubectl get nodes -o jsonpath='{.items[0].status.conditions[-1].type}'"
    )
    assert result.stdout.strip() == 'Ready'
```

#### `controller` — unit flags

```python
def test_controller_unit_exists(host):
    assert host.file('/etc/systemd/system/k0scontroller.service').exists

def test_controller_unit_no_enable_worker(host):
    content = host.file('/etc/systemd/system/k0scontroller.service').content_string
    assert '--enable-worker' not in content
```

#### `worker` — token file and unit

```python
def test_token_file_exists(host):
    assert host.file('/etc/k0s/join-token').exists

def test_token_file_permissions(host):
    f = host.file('/etc/k0s/join-token')
    assert f.mode == 0o600
    assert f.user == 'root'

def test_worker_unit_exists(host):
    assert host.file('/etc/systemd/system/k0sworker.service').exists

def test_worker_unit_uses_token_file(host):
    content = host.file('/etc/systemd/system/k0sworker.service').content_string
    assert '--token-file /etc/k0s/join-token' in content
```

#### `custom-network` — config content

```python
def test_config_uses_calico(host):
    import yaml
    content = host.file('/etc/k0s/k0s.yaml').content_string
    config = yaml.safe_load(content)
    assert config['spec']['network']['provider'] == 'calico'
    assert config['spec']['network']['podCIDR'] == '192.168.0.0/16'
```

#### Idempotency (all suites)

```python
def test_idempotency(host):
    import json
    result = host.run('salt-call --local state.highstate --out=json --retcode-passthrough')
    data = json.loads(result.stdout)
    changed = [k for k, v in data['local'].items() if v.get('changes')]
    assert changed == [], f"States with unexpected changes: {changed}"
```

### 9.5 Test file layout

```
tests/
├── pillar/
│   ├── single.sls
│   ├── controller.sls
│   ├── worker.sls
│   └── custom-network.sls
└── integration/
    ├── default/
    │   ├── conftest.py
    │   └── test_k0s.py
    ├── controller/
    │   ├── conftest.py      # symlink or copy from default/
    │   └── test_k0s.py
    ├── worker/
    │   ├── conftest.py
    │   └── test_k0s.py
    └── custom-network/
        ├── conftest.py
        └── test_k0s.py
```

`conftest.py` is identical across all suites — it reads the kitchen state file
using `KITCHEN_SUITE` and `KITCHEN_PLATFORM` environment variables set by kitchen.

## Acceptance criteria

- [ ] All 4 suites run via `make tests` without infrastructure errors
- [ ] `default` suite: cluster API is reachable and node is `Ready`
- [ ] `controller` suite: unit file exists, no `--enable-worker` flag
- [ ] `worker` suite: token file and worker unit exist with correct flags
- [ ] `custom-network` suite: `calico` and custom `podCIDR` appear in config
- [ ] Idempotency test passes for all suites (`Changed: 0` on second converge)
- [ ] HTML reports generated at `reports/report-<suite>.html`
