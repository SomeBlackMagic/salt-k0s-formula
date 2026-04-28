# Stage 5 — Worker Role (`worker.sls`)

## Goal

Write the join token to disk and install the k0s systemd unit for the worker role.

## Deliverables

### 5.1 Validation

Fail early with a descriptive error if either of these pillars is missing or empty:
- `k0s.worker.join_token`
- `k0s.worker.api_address`

### 5.2 Token file

1. Write `k0s.worker.join_token` to `/etc/k0s/join-token`
2. Permissions: `0600`, owner `root:root`
3. Directory `/etc/k0s/` must exist (created by `config.sls` or by this state if role is `worker`)

### 5.3 Unit installation

Run `k0s install worker` with the following flags:
- `--token-file /etc/k0s/join-token`
- `--api-server https://{{ k0s.worker.api_address }}`
- `--profile {{ k0s.worker.profile }}`
- `--data-dir {{ k0s.data_dir }}`
- Append `k0s.extra_args` if set

Expected systemd unit name: `k0sworker`

### 5.4 Relation to other states

```
install.sls  →  worker.sls  →  service.sls
```

Worker role does NOT include `config.sls` — workers have no `k0s.yaml`.

### 5.5 Idempotency

- Token file write is idempotent (no change if contents are identical)
- `k0s install worker` is only re-run if the unit file does not exist
  (use `unless: systemctl cat k0sworker`)

## Acceptance criteria

- [ ] `/etc/k0s/join-token` exists with mode `0600`
- [ ] `/etc/systemd/system/k0sworker.service` exists after converge
- [ ] Unit contains `--token-file /etc/k0s/join-token`
- [ ] State fails clearly when `join_token` or `api_address` is missing
- [ ] Second converge produces `Changed: 0`
