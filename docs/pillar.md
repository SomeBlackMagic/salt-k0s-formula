# Pillar Reference

The formula reads its configuration from the `k0s` pillar namespace.
If a value is not set, the state files use defaults matching `k0s/defaults.yaml`.

## Full Schema

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
      api:
        address: ''
        sans: []
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

  token:
    ttl: 24
    path: /etc/k0s/worker-join-token

  service:
    enabled: true
    running: true
```

## Required Values by Role

| Parameter                |    `single` | `controller` |    `worker` |
|--------------------------|------------:|-------------:|------------:|
| `k0s.role`               |         yes |          yes |         yes |
| `k0s.version`            | recommended |  recommended | recommended |
| `k0s.worker.join_token`  |          no |           no |         yes |
| `k0s.worker.api_address` |          no |           no |         yes |

If `k0s.role` is not set, the formula uses `single`.

## `k0s.version`

k0s release tag, for example:

```yaml
k0s:
  version: 'v1.30.2+k0s.0'
```

The formula builds this default download URL:

```text
https://github.com/k0sproject/k0s/releases/download/<version>/k0s-<version>-<arch>
```

The current implementation does not treat `latest` as a special value.
It will be used literally as part of the URL.

## `k0s.install`

```yaml
k0s:
  install:
    binary_url: 'https://mirror.example.internal/k0s-v1.30.2+k0s.0-amd64'
    checksum: '<sha256>'
```

- `binary_url` overrides the download URL. This is useful for air-gapped environments.
- `checksum` enables SHA256 verification through `source_hash`.
- If `checksum` is empty, the download uses `skip_verify: True`.

## `k0s.config.spec`

If `k0s.config.spec` is set, the formula renders `k0s/files/k0s.yaml.j2`
and manages `/etc/k0s/k0s.yaml`.

If `k0s.config.spec` is completely absent, `k0s.config` runs:

```bash
/usr/local/bin/k0s config create > /etc/k0s/k0s.yaml
```

Because the defaults include `config.spec`, the normal path is managed
configuration from pillar data.

### API Address

If `k0s.config.spec.api.address` is empty, the template chooses the first IPv4
address from `grains['ip4_interfaces']`, skipping `lo*` and `docker*`
interfaces. The selected address is also prepended to `spec.api.sans`.

Example with an explicit address:

```yaml
k0s:
  config:
    spec:
      api:
        address: 10.0.0.10
        sans:
          - k0s-api.example.internal
```

## `k0s.controller`

```yaml
k0s:
  controller:
    enable_worker: true
    no_taints: true
```

- `enable_worker` adds `--enable-worker`.
- `no_taints` adds `--no-taints`.

When `k0s.role` is `single`, the controller unit is installed with `--single`.
Use `enable_worker` and `no_taints` for expandable single-node-like controller
setups instead of the strict k0s single-node mode.

## `k0s.worker`

```yaml
k0s:
  worker:
    join_token: '<token>'
    api_address: '10.0.0.10:6443'
    profile: default
```

- `join_token` is written to `/etc/k0s/join-token` with mode `0600`.
- `api_address` is used for `--api-server https://<api_address>`.
- `profile` is passed as `--profile`.

## `k0s.extra_args`

`extra_args` is appended to `k0s install controller` or `k0s install worker`.

You can pass a string:

```yaml
k0s:
  extra_args: '--debug'
```

Or a list:

```yaml
k0s:
  extra_args:
    - --debug
    - --some-flag=value
```

Strings are parsed with a shell-like parser. If quoting or escaping is invalid,
the custom state fails with an error.

## `k0s.service`

```yaml
k0s:
  service:
    enabled: true
    running: true
```

- `enabled: true` enables the unit at boot.
- `running: true` starts the service.
- `running: false` stops the service.
- `enabled: false` disables the unit at boot.

## `k0s.manifests` and `k0s.manifests_map`

Kubernetes manifests to apply via `k0s kubectl apply` after the cluster
becomes operational.

### Formats

**`manifests`** — ordered list:

```yaml
k0s:
  manifests:
    - name: my-crds
      source: /srv/salt/files/crds.yaml
```

**`manifests_map`** — dictionary keyed by `name`. Useful for overriding
individual entries defined in a base role:

```yaml
k0s:
  manifests_map:
    my-crds:
      source: /srv/salt/files/crds.yaml
```

Both formats can be used together. When a `manifests_map` key matches the
`name` of a `manifests` entry, the two are **merged** (map values win on
conflict). Unmatched map keys are appended as new entries.

### Entry fields

| Field           | Required                    | Description |
|-----------------|-----------------------------|-------------|
| `name`          | yes (in `manifests`)        | Salt state identifier |
| `source`        | one of `source`/`content`   | Path to a manifest file on the minion |
| `content`       | one of `source`/`content`   | Inline YAML manifest string |
| `wait`          | no                          | Pre-conditions checked before apply (see below) |
| `template`      | no                          | `true` — render as Jinja2 before applying |
| `template_vars` | no                          | Extra variables available inside the template |

`source` and `content` may both be set; their contents are concatenated
before applying.

### Pre-conditions (`wait`)

`wait` is a list of conditions checked via `kubectl wait` **before**
`kubectl apply`. If any condition fails, the manifest is not applied.

```yaml
k0s:
  manifests:
    - name: my-app
      source: /srv/salt/files/app.yaml
      wait:
        - for: condition=Established
          resource: crd/myresources.example.com
          timeout: 60s
        - for: condition=Available
          resource: deployment/dependency
          namespace: infra
          timeout: 120s
```

| Key         | Required | Description |
|-------------|----------|-------------|
| `for`       | yes      | Condition passed to `--for`, e.g. `condition=Established` |
| `resource`  | yes      | Resource reference, e.g. `crd/foo.example.com` |
| `timeout`   | no       | Duration passed to `--timeout`, e.g. `60s`, `2m` (kubectl default: 30s) |
| `namespace` | no       | Namespace passed to `-n` (required for namespace-scoped resources) |

If the resource does not exist yet (`NotFound`), `wait` retries automatically
until `timeout` is exceeded.

### Jinja2 templates

Set `template: true` to render `content` and `source` file contents as
Jinja2 before applying.

Variables available inside the template:

| Variable      | Contains |
|---------------|----------|
| `pillar`      | Salt pillar data (`__pillar__`) |
| `grains`      | Salt grains (`__grains__`) |
| `opts`        | Salt opts (`__opts__`) |
| `salt`        | Salt execution modules (`__salt__`) |
| *(any name)*  | Keys from `template_vars` |

```yaml
k0s:
  manifests:
    - name: app-config
      template: true
      template_vars:
        environment: production
        replicas: 3
      content: |
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: my-app
          namespace: {{ environment }}
        spec:
          replicas: {{ replicas }}
          selector:
            matchLabels:
              app: my-app
          template:
            metadata:
              labels:
                app: my-app
            spec:
              containers:
                - name: my-app
                  image: my-app:{{ pillar['my_app']['version'] }}
```

### Examples

**Source file only:**

```yaml
k0s:
  manifests:
    - name: nginx
      source: /srv/salt/k0s/files/nginx.yaml
```

**Inline content only:**

```yaml
k0s:
  manifests:
    - name: coredns-config
      content: |
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: coredns-custom
          namespace: kube-system
        data:
          log.override: |
            log
```

**Source file and inline content (concatenated):**

```yaml
k0s:
  manifests:
    - name: app-with-quota
      source: /srv/salt/k0s/files/namespace.yaml
      content: |
        apiVersion: v1
        kind: ResourceQuota
        metadata:
          name: default-quota
          namespace: my-app
        spec:
          hard:
            pods: "10"
```

**CRDs with a wait condition before installing the operator:**

```yaml
k0s:
  manifests:
    - name: external-secrets-crds
      source: /srv/salt/k0s/files/external-secrets-crds.yaml

    - name: external-secrets-operator
      source: /srv/salt/k0s/files/external-secrets.yaml
      wait:
        - for: condition=Established
          resource: crd/clustersecretstores.external-secrets.io
          timeout: 60s

  manifests_map:
    # Override the wait condition for a specific environment
    external-secrets-crds:
      wait:
        - for: condition=Established
          resource: crd/externalsecrets.external-secrets.io
          timeout: 90s
```
