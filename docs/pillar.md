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

| Parameter | `single` | `controller` | `worker` |
|---|---:|---:|---:|
| `k0s.role` | yes | yes | yes |
| `k0s.version` | recommended | recommended | recommended |
| `k0s.worker.join_token` | no | no | yes |
| `k0s.worker.api_address` | no | no | yes |

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

Both options are usually needed for a single-node cluster.

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
