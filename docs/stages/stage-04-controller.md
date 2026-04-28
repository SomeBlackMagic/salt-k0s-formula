# Stage 4 — Controller Role (`controller.sls`)

## Goal

Install the k0s systemd unit for the controller role using `k0s install controller`.

## Deliverables

### 4.1 Logic

1. Run `k0s install controller` to create the systemd unit file
   - Add `--enable-worker` if `k0s.controller.enable_worker == true`
   - Add `--no-taints` if `k0s.controller.no_taints == true`
   - Append `k0s.extra_args` if set
   - Pass `--config {{ k0s.config_path }}`
   - Pass `--data-dir {{ k0s.data_dir }}`
2. The command is only re-run if the unit file does not exist or the install arguments have changed

### 4.2 Systemd unit

`k0s install controller` creates `/etc/systemd/system/k0scontroller.service`.
The formula does not manage this file directly — it relies on `k0s install` to produce it.

Expected service name: `k0scontroller`

### 4.3 Relation to other states

```
install.sls  →  controller.sls  →  service.sls
config.sls   ↗
```

- `controller.sls` requires `install.sls` to have run (binary must exist)
- `controller.sls` requires `config.sls` to have run (config file must exist)
- `service.sls` requires `controller.sls` to have run (unit file must exist)

### 4.4 Idempotency

- `k0s install controller` is idempotent by itself — calling it when the unit already exists
  produces no changes
- The state must detect this and report `Changed: 0` accordingly
  (use `unless: systemctl cat k0scontroller` or check the unit file exists)

## Acceptance criteria

- [ ] `/etc/systemd/system/k0scontroller.service` exists after converge
- [ ] `--enable-worker` flag is present in the unit when `controller.enable_worker: true`
- [ ] `--no-taints` flag is present in the unit when `controller.no_taints: true`
- [ ] Second converge produces `Changed: 0`
- [ ] State fails clearly if binary is not installed
