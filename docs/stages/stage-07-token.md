# Stage 7 — Join Token Management (`token.sls`)

## Goal

Generate a worker join token on the controller node and make it available
to worker nodes via Salt Mine.

## Deliverables

### 7.1 When to apply

`token.sls` is NOT included by `init.sls` automatically.
It is a standalone state applied explicitly on controller nodes when worker nodes need to join:

```bash
salt '<controller>' state.apply k0s.token
```

### 7.2 Token generation

1. Run `k0s token create --role worker` on the controller node
2. Capture stdout as the token value
3. Write the token to `/etc/k0s/worker-join-token` (mode `0600`, owner `root:root`)
4. Re-generate only if the file does not exist or is older than `token.ttl` hours

Token TTL pillar (added in this stage):

```yaml
k0s:
  token:
    # Hours after which the token is considered expired and regenerated
    # 0 = never regenerate if file exists
    ttl: 24
    # Path where the token is stored on the controller
    path: /etc/k0s/worker-join-token
```

### 7.3 Salt Mine distribution

1. Publish the token via Salt Mine so worker nodes can retrieve it:

```yaml
# In master config or minion config:
mine_functions:
  k0s_worker_token:
    mine_function: cmd.run
    cmd: cat /etc/k0s/worker-join-token
```

2. Worker nodes can then read the token in their pillar via:

```jinja
{% set token = salt['mine.get']('controller_minion_id', 'k0s_worker_token').values() | first %}
```

### 7.4 Scope limitations

- Multi-controller HA token distribution is out of scope
- Token rotation (revoking old tokens) is a manual operation
- This stage does not configure Salt Mine automatically —
  Mine setup is expected to be handled by a separate formula or base state

## Acceptance criteria

- [ ] `/etc/k0s/worker-join-token` is created on the controller after `state.apply k0s.token`
- [ ] File has mode `0600`, owner `root:root`
- [ ] Token is non-empty and valid (passes `k0s token list` check)
- [ ] Re-applying the state within TTL does not regenerate the token (`Changed: 0`)
- [ ] Re-applying after TTL expires regenerates the token
