# k0s Salt Formula

Usage documentation for the Salt formula that installs and manages k0s.

The formula installs the k0s binary, generates controller configuration,
creates a systemd unit through `k0s install controller` or `k0s install worker`,
and manages the service.

## Supported Features

| Feature | Status |
|---|---|
| Install the k0s binary to `/usr/local/bin/k0s` | supported |
| `single` role | supported |
| `controller` role | supported |
| `worker` role | supported |
| Generate `/etc/k0s/k0s.yaml` | supported for `single` and `controller` |
| Generate a worker join token on the controller | supported through the standalone `k0s.token` state |
| Manage the systemd service | supported |
| Full k0s removal | not implemented yet; `k0s.uninstall` is a placeholder |

Supported binary download architectures: `amd64`, `arm64`, `aarch64`.

## Documents

- [quickstart.md](quickstart.md) - minimal setup for single-node, controller, and worker nodes.
- [pillar.md](pillar.md) - the full pillar contract and examples.
- [states.md](states.md) - available state files and their behavior.
- [operations.md](operations.md) - tokens, upgrades, service management, and limitations.
- [testing.md](testing.md) - local unit and integration tests.
- [stages/](stages/) - historical development-stage documentation.

## Minimal Single-Node Example

```yaml
k0s:
  role: single
  version: 'v1.30.2+k0s.0'
  config:
    spec:
      telemetry:
        enabled: false
```

Apply it:

```bash
salt '<minion-id>' saltutil.sync_states
salt '<minion-id>' state.apply k0s
```

Check the node:

```bash
/usr/local/bin/k0s version
systemctl status k0scontroller
/usr/local/bin/k0s kubectl get nodes
```

## Salt Environment Requirements

The formula uses custom state modules from `k0s/_states/`:

- `k0s_controller.installed`
- `k0s_worker.installed`

Salt synchronizes custom state modules from an `_states` directory at the
Salt file-root level. Before applying the formula in a regular Salt
master/minion environment, expose `k0s/_states` as file-root `_states`
using your deployment tooling, a copy, or a symlink, then synchronize the
modules:

```bash
salt '<minion-id>' saltutil.sync_states
```

The formula must be available in Salt file roots so that `salt://k0s/...`
resolves to the `k0s/` directory, and the custom modules must be available
as `_states/` for `saltutil.sync_states`.
