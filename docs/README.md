# k0s Salt Formula — Development Specification

k0s is a minimal Kubernetes distribution shipped as a single binary.
This formula automates installation and configuration of k0s nodes.

## Supported roles

| Role | Description |
|---|---|
| `controller` | Control plane node |
| `worker` | Worker node, joins an existing cluster |
| `single` | Combined controller + worker, for dev/test |

## Supported platforms

| OS | Versions |
|---|---|
| Ubuntu | 22.04, 24.04 |
| Debian | 11, 12 |

Architectures: `amd64`, `arm64`.

## Development stages

| Stage | File | Description |
|---|---|---|
| 1 | [stage-01-structure.md](stages/stage-01-structure.md) | Repository layout and pillar schema |
| 2 | [stage-02-install.md](stages/stage-02-install.md) | Binary installation (`install.sls`) |
| 3 | [stage-03-config.md](stages/stage-03-config.md) | Configuration file generation (`config.sls`) |
| 4 | [stage-04-controller.md](stages/stage-04-controller.md) | Controller role (`controller.sls`) |
| 5 | [stage-05-worker.md](stages/stage-05-worker.md) | Worker role (`worker.sls`) |
| 6 | [stage-06-service.md](stages/stage-06-service.md) | Service management (`service.sls`) |
| 7 | [stage-07-token.md](stages/stage-07-token.md) | Join token management (`token.sls`) |
| 8 | [stage-08-uninstall.md](stages/stage-08-uninstall.md) | Uninstall (`uninstall.sls`) |
| 9 | [stage-09-testing.md](stages/stage-09-testing.md) | Kitchen suites and testinfra tests |

## General requirements

- Every state must be **idempotent**: a second `kitchen converge` must produce `Changed: 0`
- No hardcoded values — everything is driven by pillars
- Service restarts only when configuration or binary actually changed
- All stages must pass `make tests` before being considered complete
