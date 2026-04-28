# Stage 2 — Binary Installation (`install.sls`)

## Goal

Download the k0s binary for the correct architecture, verify its integrity,
and place it at `/usr/local/bin/k0s`.

## Deliverables

### 2.1 Logic

1. Resolve the target architecture from `grains['osarch']`:
   - `amd64` → `k0s-<version>-amd64`
   - `arm64` / `aarch64` → `k0s-<version>-arm64`
2. Build the download URL:
   - Default: `https://github.com/k0sproject/k0s/releases/download/<version>/k0s-<version>-<arch>`
   - Override: `k0s.install.binary_url` if set
3. Download to a temporary path, then move to `/usr/local/bin/k0s`
4. If `k0s.install.checksum` is set — verify SHA256 before placement, fail the state if mismatch
5. Set permissions `0755`, owner `root:root`
6. Skip download if already installed and version matches:
   - Run `k0s version` and compare output against `k0s.version`

### 2.2 Idempotency

- The state must report `Changed: 0` on a second run when the correct version is already installed
- Version comparison must handle the `+k0s.0` suffix in release tags

### 2.3 Upgrade path

- When `k0s.version` differs from the installed version, the binary is replaced
- Replacement triggers a service restart via `watch_in` on `service.sls`

## Acceptance criteria

- [ ] Binary exists at `/usr/local/bin/k0s`
- [ ] Binary is executable (`mode 0755`, owner `root:root`)
- [ ] `k0s version` output matches `k0s.version` pillar
- [ ] Second `kitchen converge` produces `Changed: 0`
- [ ] Works on both `amd64` and `arm64`
- [ ] State fails with a clear error if checksum does not match
