# Stage 8 — Uninstall (`uninstall.sls`)

## Goal

Completely remove k0s and all its data from the node.

## Deliverables

### 8.1 Logic (in order)

1. **Stop the service** — `systemctl stop k0scontroller` or `k0sworker`
   - Skip gracefully if the service does not exist
2. **Reset k0s data** — run `k0s reset`
   - Removes CNI configs, etcd data, certificates, kubeconfig
   - Skip if k0s binary does not exist
3. **Uninstall the systemd unit** — run `k0s uninstall controller` or `k0s uninstall worker`
   - Skip if the unit file does not exist
4. **Remove files and directories**:
   - `/usr/local/bin/k0s`
   - `/etc/k0s/` (entire directory)
   - `k0s.data_dir` (default `/var/lib/k0s`)
5. **Reload systemd** — `systemctl daemon-reload`

### 8.2 Safety

- `uninstall.sls` is NOT included by `init.sls`
- Must be applied explicitly:
  ```bash
  salt '<minion>' state.apply k0s.uninstall
  ```
- Each step must be guarded so the state does not fail if a resource is already absent

### 8.3 Idempotency

- Running `uninstall.sls` twice must not raise errors
- All steps use `onlyif` / `unless` guards checking for resource existence

## Acceptance criteria

- [ ] After applying `uninstall.sls`:
  - `k0s version` returns a non-zero exit code (binary gone)
  - `/etc/k0s/` directory does not exist
  - `k0s.data_dir` does not exist
  - `systemctl status k0scontroller` returns "not found"
- [ ] Applying `uninstall.sls` twice does not fail
- [ ] State is safe to run even if k0s was never installed
