# Stage 1 — Repository Layout and Pillar Schema

## Goal

Define the file structure of the formula and the full pillar schema that all subsequent
stages will rely on. No Salt states are written in this stage — only skeletons and data contracts.

## Deliverables

### 1.1 Formula file structure

```
k0s/
├── init.sls          # Entry point — routes to role-specific states
├── install.sls       # Binary download and placement
├── config.sls        # /etc/k0s/k0s.yaml generation
├── controller.sls    # systemd unit install for controller role
├── worker.sls        # systemd unit install for worker role
├── service.sls       # Service enable/start management
├── token.sls         # Join token generation and distribution
├── uninstall.sls     # Full removal of k0s
└── defaults.yaml     # Pillar defaults (merged via pillar.stack or map.jinja)
```

### 1.2 `init.sls` routing logic

```
k0s.role == 'controller'  →  include: install, config, controller, service
k0s.role == 'worker'      →  include: install, worker, service
k0s.role == 'single'      →  include: install, config, controller (enable_worker=true), service
```

### 1.3 Full pillar schema

```yaml
k0s:
  # k0s release tag. Use 'latest' to resolve the latest stable release at apply time.
  version: 'v1.30.2+k0s.0'

  # Node role: controller | worker | single
  role: controller

  # Path to the k0s configuration file
  config_path: /etc/k0s/k0s.yaml

  # k0s data directory
  data_dir: /var/lib/k0s

  # Extra CLI flags appended to the k0s service command line
  extra_args: ''

  install:
    # Override the binary download URL (e.g. for air-gapped environments or mirrors)
    binary_url: ''
    # Expected SHA256 checksum of the downloaded binary. Verified before placement.
    checksum: ''

  config:
    # Contents of k0s.yaml under the 'spec' key.
    # If omitted, the output of 'k0s config create' is used as-is.
    spec:
      api:
        # IP address advertised by kube-apiserver.
        # Defaults to the first non-loopback IP if empty.
        address: ''
        # Additional Subject Alternative Names for the API TLS certificate
        sans: []
      network:
        # CNI provider: kuberouter | calico | custom
        provider: kuberouter
        podCIDR: 10.244.0.0/16
        serviceCIDR: 10.96.0.0/12
      storage:
        # etcd (default) | kine (SQLite-backed, for single-node)
        type: etcd
      telemetry:
        enabled: false

  controller:
    # Run a worker on the same node (equivalent to --enable-worker flag)
    enable_worker: false
    # Remove the default taint from control-plane node (allow regular pods to schedule)
    no_taints: false

  worker:
    # Join token obtained via: k0s token create --role worker
    # Required when role == 'worker'
    join_token: ''
    # kube-apiserver address reachable from this worker node
    # Required when role == 'worker'
    api_address: ''
    # Worker profile: default | light
    profile: default

  service:
    # Whether to enable the systemd unit (start on boot)
    enabled: true
    # Whether to ensure the service is running right now
    running: true
```

### 1.4 Required fields by role

| Pillar | controller | worker | single |
|---|---|---|---|
| `k0s.role` | ✓ | ✓ | ✓ |
| `k0s.version` | ✓ | ✓ | ✓ |
| `k0s.worker.join_token` | — | ✓ | — |
| `k0s.worker.api_address` | — | ✓ | — |

### 1.5 `defaults.yaml`

Provides sane defaults so that a minimal pillar only needs to set `role` and `version`:

```yaml
k0s:
  version: 'v1.30.2+k0s.0'
  role: single
  config_path: /etc/k0s/k0s.yaml
  data_dir: /var/lib/k0s
  extra_args: ''
  install:
    binary_url: ''
    checksum: ''
  config:
    spec:
      network:
        provider: kuberouter
        podCIDR: 10.244.0.0/16
        serviceCIDR: 10.96.0.0/12
      storage:
        type: etcd
      telemetry:
        enabled: false
  controller:
    enable_worker: false
    no_taints: false
  worker:
    join_token: ''
    api_address: ''
    profile: default
  service:
    enabled: true
    running: true
```

## Acceptance criteria

- [ ] All `.sls` files exist (may be empty stubs at this stage)
- [ ] `defaults.yaml` is present and parseable
- [ ] `init.sls` contains the routing `include` logic for all three roles
- [ ] `make tests` passes (converge succeeds, placeholder state runs)
