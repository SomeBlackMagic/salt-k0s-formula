# Quickstart

## 1. Connect the Formula to Salt

Place the repository, or its relevant contents, in Salt file roots. At minimum
you need:

```text
_states/
k0s/
```

Example `top.sls`:

```yaml
base:
  'k0s-*':
    - k0s
```

Before the first run, synchronize the custom state modules:

```bash
salt 'k0s-*' saltutil.sync_states
```

## 2. Single-Node Cluster

Single-node mode uses the controller service `k0scontroller`.
To run regular workload pods on the same node, enable the worker and remove
the control-plane taint:

```yaml
k0s:
  role: single
  version: 'v1.30.2+k0s.0'
  controller:
    enable_worker: true
    no_taints: true
  config:
    spec:
      api:
        sans:
          - k0s.local
      telemetry:
        enabled: false
```

Apply it:

```bash
salt '<single-minion>' state.apply k0s
```

Check it:

```bash
salt '<single-minion>' cmd.run '/usr/local/bin/k0s kubectl get nodes'
```

## 3. Controller-Only Node

```yaml
k0s:
  role: controller
  version: 'v1.30.2+k0s.0'
  controller:
    enable_worker: false
    no_taints: false
  config:
    spec:
      api:
        address: 10.0.0.10
        sans:
          - k0s-api.example.internal
      network:
        provider: kuberouter
        podCIDR: 10.244.0.0/16
        serviceCIDR: 10.96.0.0/12
      storage:
        type: etcd
      telemetry:
        enabled: false
```

Apply it:

```bash
salt '<controller-minion>' state.apply k0s
```

## 4. Worker Node

The worker role requires an existing join token and API server address.

```yaml
k0s:
  role: worker
  version: 'v1.30.2+k0s.0'
  worker:
    join_token: '<token-from-controller>'
    api_address: '10.0.0.10:6443'
    profile: default
```

The formula adds the `https://` scheme itself, so pass `host:port` in
`api_address`, not a full URL.

Apply it:

```bash
salt '<worker-minion>' state.apply k0s
```

## 5. Getting a Worker Token

On the controller node:

```bash
salt '<controller-minion>' state.apply k0s.token
salt '<controller-minion>' cmd.run 'cat /etc/k0s/worker-join-token'
```

Copy the value into `k0s.worker.join_token` for worker nodes.
This formula does not configure automatic Salt Mine publication.
