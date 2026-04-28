# State Reference

## `k0s`

Entry point. Includes different state files depending on `k0s.role`.

| Role | Include |
|---|---|
| `single` | `k0s.install`, `k0s.config`, `k0s.controller`, `k0s.service` |
| `controller` | `k0s.install`, `k0s.config`, `k0s.controller`, `k0s.service` |
| `worker` | `k0s.install`, `k0s.worker`, `k0s.service` |

If the role is not `single`, `controller`, or `worker`, `k0s.init` does not
include any role-specific states. If applied directly, `k0s.service` fails for
an unknown role.

## `k0s.install`

Installs `/usr/local/bin/k0s`.

Main behavior:

- resolves the architecture from `grains['osarch']`;
- downloads the release binary to `/tmp/k0s-<version>-<arch>`;
- copies the file to `/usr/local/bin/k0s`;
- sets owner `root:root` and mode `0755`;
- skips download and copy when the installed binary already reports the
  requested version through `/usr/local/bin/k0s version`.

An unsupported architecture results in `test.fail_without_changes`.

## `k0s.config`

Manages controller configuration:

- creates the directory for `k0s.config_path`;
- renders `salt://k0s/files/k0s.yaml.j2` when `k0s.config.spec` is set;
- runs `k0s config create` once when `k0s.config.spec` is absent;
- sets owner `root:root` and mode `0600`.

This state is applied for the `single` and `controller` roles.
The worker role does not create `/etc/k0s/k0s.yaml`.

## `k0s.controller`

Creates the systemd unit through the custom state `k0s_controller.installed`.

The module builds this command:

```text
/usr/local/bin/k0s install controller --config <config_path> --data-dir <data_dir> [flags]
```

Supported flags from pillar:

- `k0s.controller.enable_worker` -> `--enable-worker`
- `k0s.controller.no_taints` -> `--no-taints`
- `k0s.extra_args` -> additional arguments

The module checks the existing unit at `/etc/systemd/system/k0scontroller.service`.
If the unit already contains the requested arguments, installation is not run
again. If the unit exists but the arguments differ, the command is run with
`--force`.

## `k0s.worker`

Prepares a worker node.

Behavior:

- requires non-empty `k0s.worker.join_token` and `k0s.worker.api_address`;
- creates `/etc/k0s`;
- writes the token to `/etc/k0s/join-token` with mode `0600`;
- creates the systemd unit through the custom state `k0s_worker.installed`.

The module builds this command:

```text
/usr/local/bin/k0s install worker --token-file /etc/k0s/join-token --api-server https://<api_address> --profile <profile> --data-dir <data_dir> [flags]
```

For k0s versions where `k0s install worker --help` does not expose
`--api-server`, the custom state appends `--api-server` to `ExecStart` after
creating the unit.

## `k0s.service`

Manages the systemd service.

| Role | Service |
|---|---|
| `single` | `k0scontroller` |
| `controller` | `k0scontroller` |
| `worker` | `k0sworker` |

If `k0s.service.running: true`, the state uses `service.running`.
For `single` and `controller`, it runs this readiness check after service start:

```bash
/usr/local/bin/k0s kubectl get nodes
```

Timeout: 120 seconds, interval: 5 seconds.

If `k0s.service.running: false`, the state uses `service.dead`.

## `k0s.token`

Standalone state. It is not included by `k0s.init`.

Creates a worker join token on the controller node:

```bash
/usr/local/bin/k0s token create --role worker > /etc/k0s/worker-join-token
```

The path is configured through `k0s.token.path`; TTL in hours is configured
through `k0s.token.ttl`. If `ttl: 0`, an existing non-empty token file is always
considered current.

## `k0s.uninstall`

The current implementation is a placeholder:

```yaml
k0s_uninstall_placeholder:
  test.succeed_without_changes
```

It does not stop the service, remove the binary, or clean the data directory.
Do not use this state as an uninstall procedure until a real uninstall workflow
is implemented.
