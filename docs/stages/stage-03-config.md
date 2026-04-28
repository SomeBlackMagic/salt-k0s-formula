# Stage 3 — Configuration File Generation (`config.sls`)

## Goal

Create `/etc/k0s/k0s.yaml` from pillar data. Changes to the config file
must trigger a service restart.

## Deliverables

### 3.1 Logic

1. Ensure directory `/etc/k0s/` exists (`mode 0755`, owner `root:root`)
2. Generate `/etc/k0s/k0s.yaml`:
   - If `k0s.config.spec` is defined in pillars — render the file from a Jinja2 template
     merging pillar values into the full k0s config structure
   - If `k0s.config.spec` is not defined — run `k0s config create` and save its output as-is
3. Set permissions `0600`, owner `root:root`
4. Any change to the file content triggers a restart of the k0s service (`watch_in`)

### 3.2 Jinja2 template structure

The template (`k0s/files/k0s.yaml.j2`) must produce a valid k0s config YAML.
Minimal rendered output example:

```yaml
apiVersion: k0s.k0sproject.io/v1beta1
kind: ClusterConfig
metadata:
  name: k0s
spec:
  api:
    address: {{ api_address }}
    sans:
      {{ sans | to_yaml | indent(6) }}
  network:
    provider: {{ network.provider }}
    podCIDR: {{ network.podCIDR }}
    serviceCIDR: {{ network.serviceCIDR }}
  storage:
    type: {{ storage.type }}
  telemetry:
    enabled: {{ telemetry.enabled | lower }}
```

### 3.3 API address resolution

If `k0s.config.spec.api.address` is empty:
- Use `grains['ip4_interfaces']` to find the first non-loopback, non-docker IPv4 address
- This address is also prepended to `sans` automatically

### 3.4 Idempotency

- File content is compared before writing — no change reported if content is identical
- `k0s config create` is only called when `k0s.config.spec` is absent AND the file does not yet exist

## Acceptance criteria

- [ ] `/etc/k0s/k0s.yaml` exists after converge
- [ ] File has mode `0600`, owner `root:root`
- [ ] Values from `k0s.config.spec` pillar are reflected in the file
- [ ] Changing a pillar value and re-converging updates the file and restarts the service
- [ ] Second converge with no pillar changes produces `Changed: 0`
- [ ] File is valid YAML and passes `k0s config validate`
