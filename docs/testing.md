# Testing

## Local Setup

```bash
make setup
```

This target performs:

- system dependency installation through `apt-get`;
- `bundle install`;
- Python virtualenv creation;
- installation from `requirements.txt`;
- Docker image build for `salt-kitchen:ubuntu-22.04`.

## Unit Tests

```bash
make unit_tests
```

Unit tests cover the custom state modules:

- `_states/k0s_controller.py`
- `_states/k0s_worker.py`

Main checks:

- test mode does not change the system;
- missing prerequisites produce clear errors;
- the `k0s install ...` command is built with expected arguments;
- repeated runs are idempotent when the unit already contains the requested arguments;
- `--force` is used when arguments change.

## Integration Tests

```bash
make integration_tests
```

Integration tests run through Test Kitchen in a privileged Docker container.
The current `.kitchen.yml` contains the `default` suite on the
`salt-kitchen:ubuntu-22.04` image.

Tests are located in:

```text
tests/integration/default/
```

The HTML report is written to:

```text
reports/report-default.html
```

## All Tests

```bash
make tests
```

This target runs unit tests and integration tests.

## Cleanup

```bash
make clean
```

Removes the Test Kitchen environment, `.venv`, and `reports`.

## Notes

Integration tests require Docker, a systemd-capable container, and network
access to download the k0s binary unless the binary is replaced through a mirror
or cache.
