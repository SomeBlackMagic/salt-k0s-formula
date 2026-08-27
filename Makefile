.PHONY: help setup system-deps virtualenv bundle-install build-image \
        lint lint-yaml lint-salt \
        unit-tests integration-tests tests \
        converge verify destroy login \
        clean

KITCHEN   := bundle exec kitchen
SUITE     := default
PLATFORM  := ubuntu
VENV      := .venv
PY        := $(VENV)/bin/python
PIP       := $(VENV)/bin/pip
PYTEST    := $(VENV)/bin/pytest
YAMLLINT  := $(VENV)/bin/yamllint
SALTLINT  := $(VENV)/bin/salt-lint

# ─── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup:"
	@echo "  setup              Install all dependencies (system + python + ruby + docker image)"
	@echo "  system-deps        Install system packages (ruby-dev, python3-venv, libyaml-dev)"
	@echo "  virtualenv         Create Python venv and install requirements.txt"
	@echo "  bundle-install     Install Ruby gems (test-kitchen, kitchen-docker, kitchen-salt)"
	@echo "  build-image        Build the Salt test Docker image (salt-kitchen:ubuntu-22.04)"
	@echo ""
	@echo "Lint:"
	@echo "  lint               Run yamllint + salt-lint"
	@echo "  lint-yaml          Run yamllint only"
	@echo "  lint-salt          Run salt-lint on *.sls files only"
	@echo ""
	@echo "Tests:"
	@echo "  unit-tests         Run pytest unit tests (no Docker required)"
	@echo "  integration-tests  Run integration tests via Test Kitchen"
	@echo "  tests              Run lint + unit-tests + integration-tests"
	@echo ""
	@echo "Kitchen:"
	@echo "  converge           Apply Salt states to the test container"
	@echo "  verify             Run integration tests against running container"
	@echo "  destroy            Destroy the test container"
	@echo "  login              Open shell in running container  [PLATFORM=$(PLATFORM)]"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean              Destroy Kitchen instance and remove generated files"

# ─── Setup ─────────────────────────────────────────────────────────────────────

system-deps:
	sudo apt-get install -y ruby-dev python3-venv libyaml-dev

# Rebuild venv only when requirements.txt changes.
$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt
	touch $(VENV)/.installed

virtualenv: $(VENV)/.installed

# Rebuild bundle only when Gemfile changes.
vendor/bundle/.installed: Gemfile
	bundle config set --local path vendor/bundle
	bundle install
	touch vendor/bundle/.installed

bundle-install: vendor/bundle/.installed

build-image:
	DOCKER_BUILDKIT=0 docker build -f Dockerfile.kitchen -t salt-kitchen:ubuntu-22.04 .

setup: system-deps virtualenv bundle-install build-image

# ─── Lint ──────────────────────────────────────────────────────────────────────

lint-yaml: virtualenv
	$(YAMLLINT) -s .

lint-salt: virtualenv
	git ls-files -- '*.sls' | xargs --no-run-if-empty $(SALTLINT)

lint: lint-yaml lint-salt

# ─── Tests ─────────────────────────────────────────────────────────────────────

# Create the _states symlink that salt-call needs when running locally.
_states:
	ln -s k0s/_states _states

unit-tests: virtualenv
	$(PYTEST) tests/unit/ -v

integration-tests: _states bundle-install
	mkdir -p reports
	DOCKER_BUILDKIT=0 $(KITCHEN) test --destroy=always

tests: lint unit-tests integration-tests

# ─── Kitchen ───────────────────────────────────────────────────────────────────

converge: bundle-install _states
	$(KITCHEN) converge $(SUITE)-$(PLATFORM)

verify: bundle-install
	$(KITCHEN) verify $(SUITE)-$(PLATFORM)

destroy: bundle-install
	$(KITCHEN) destroy $(SUITE)-$(PLATFORM)

login: bundle-install
	$(KITCHEN) login $(SUITE)-$(PLATFORM)

# ─── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	-$(KITCHEN) destroy
	rm -rf $(VENV) reports _states
