# Stage 6 — Service Management (`service.sls`)

## Goal

Enable and start the k0s systemd service. React to changes in config or binary.

## Deliverables

### 6.1 Service name resolution

Determine the service name from the role:

| Role | Service name |
|---|---|
| `controller` | `k0scontroller` |
| `worker` | `k0sworker` |
| `single` | `k0scontroller` |

### 6.2 Logic

1. Enable the service if `k0s.service.enabled == true` (`systemctl enable`)
2. Start the service if `k0s.service.running == true` (`systemctl start`)
3. If `k0s.service.enabled == false` — disable the service
4. If `k0s.service.running == false` — stop the service

### 6.3 Restart triggers

The service must be restarted (not just notified) when:
- The k0s binary is replaced (new version installed) — via `watch` on `install.sls`
- `/etc/k0s/k0s.yaml` content changes — via `watch` on `config.sls`

### 6.4 Startup wait

After starting the service, the formula must wait until k0s is operational:
- For `controller` / `single`: poll until `k0s kubectl get nodes` returns exit code 0
  (timeout: 120 seconds, interval: 5 seconds)
- For `worker`: poll until the node appears in `k0s kubectl get nodes` on the controller
  (out of scope for this stage — documented in stage-07)

### 6.5 Relation to other states

```
controller.sls | worker.sls  →  service.sls
install.sls    ─────────────↗  (restart trigger)
config.sls     ─────────────↗  (restart trigger)
```

## Acceptance criteria

- [ ] Service is enabled and running after converge
- [ ] `systemctl is-active k0scontroller` returns `active`
- [ ] `systemctl is-enabled k0scontroller` returns `enabled`
- [ ] Changing `/etc/k0s/k0s.yaml` and re-converging restarts the service
- [ ] Replacing the binary and re-converging restarts the service
- [ ] Setting `k0s.service.running: false` stops the service
- [ ] Second converge produces `Changed: 0`
