# Operations

## Checking Cluster State

For `single` and `controller`:

```bash
salt '<controller-minion>' cmd.run '/usr/local/bin/k0s version'
salt '<controller-minion>' cmd.run 'systemctl is-active k0scontroller'
salt '<controller-minion>' cmd.run '/usr/local/bin/k0s kubectl get nodes'
```

For workers:

```bash
salt '<worker-minion>' cmd.run 'systemctl is-active k0sworker'
salt '<worker-minion>' cmd.run 'systemctl cat k0sworker'
```

## Join Token for Worker Nodes

Create a token on the controller node:

```bash
salt '<controller-minion>' state.apply k0s.token
```

By default, the token is stored at:

```text
/etc/k0s/worker-join-token
```

Read the token:

```bash
salt '<controller-minion>' cmd.run 'cat /etc/k0s/worker-join-token'
```

Pass the value to worker node pillar:

```yaml
k0s:
  role: worker
  worker:
    join_token: '<token>'
    api_address: '10.0.0.10:6443'
```

Reapplying `k0s.token` does not change the token while the file exists and is
not older than `k0s.token.ttl` hours. With `ttl: 0`, the token is not
regenerated as long as the file exists and is non-empty.

## Upgrade k0s

1. Update `k0s.version` in pillar.
2. Set a new `k0s.install.checksum` if needed.
3. Apply the state:

```bash
salt '<minion-id>' state.apply k0s
```

`k0s.install` replaces the binary if `/usr/local/bin/k0s version` does not
contain the requested release tag. `k0s.service` watches the binary state and
restarts the service when it changes.

For production clusters, upgrade nodes one at a time and check cluster state
between steps:

```bash
salt '<controller-minion>' cmd.run '/usr/local/bin/k0s kubectl get nodes'
```

## Change Controller Config

Change `k0s.config.spec` in pillar and apply:

```bash
salt '<controller-minion>' state.apply k0s
```

`k0s.config` updates `/etc/k0s/k0s.yaml`, and `k0s.service` restarts
`k0scontroller` through its watch relationship.

## Stop the Service Without Removing k0s

```yaml
k0s:
  service:
    enabled: false
    running: false
```

Apply it:

```bash
salt '<minion-id>' state.apply k0s
```

To enable and start it again, restore:

```yaml
k0s:
  service:
    enabled: true
    running: true
```

## Air-Gapped or Mirror Installation

Download the binary in advance and host it on an accessible Salt minion URL or
HTTP mirror:

```yaml
k0s:
  version: 'v1.30.2+k0s.0'
  install:
    binary_url: 'https://mirror.example.internal/k0s-v1.30.2+k0s.0-amd64'
    checksum: '<sha256>'
```

If the mirror serves different files for different architectures, set pillar
per target group or use separate pillar values for `amd64` and `arm64`.

## Removal

`k0s.uninstall` does not implement removal yet. The current state only succeeds
without making changes.

Until an uninstall workflow is implemented, removal must be done manually using
the procedure accepted in your infrastructure, taking into account `k0s reset`,
systemd units, `/etc/k0s`, `/var/lib/k0s`, and `/usr/local/bin/k0s`.

## Common Errors

### `k0s_controller` or `k0s_worker` state is not available

Synchronize the custom state modules:

```bash
salt '<minion-id>' saltutil.sync_states
```

### Worker state fails because of `join_token` or `api_address`

For `role: worker`, both parameters are required:

```yaml
k0s:
  worker:
    join_token: '<token>'
    api_address: '10.0.0.10:6443'
```

### Unsupported architecture

`k0s.install` supports only `amd64`, `arm64`, and `aarch64`.
Check the grain:

```bash
salt '<minion-id>' grains.get osarch
```

### Config does not contain the expected API address

If `k0s.config.spec.api.address` is empty, the address is selected
automatically from IPv4 interfaces. For predictable behavior, set the address
explicitly:

```yaml
k0s:
  config:
    spec:
      api:
        address: 10.0.0.10
```
