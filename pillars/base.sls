k0s:
  config:
    spec:
      api:
        address: ''
        sans:
          - k0s.local
      network:
        provider: kuberouter
        podCIDR: 10.244.0.0/16
        serviceCIDR: 10.96.0.0/12
      storage:
        type: etcd
      telemetry:
        enabled: false
