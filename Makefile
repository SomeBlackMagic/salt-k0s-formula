.PHONY: bundle_install tests unit_tests integration_tests prepare_extmods virtualenv setup system-deps clean build-image

system-deps:
	sudo apt-get install -y ruby-dev python3-venv libyaml-dev

bundle_install:
	bundle install

virtualenv:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

setup: system-deps bundle_install virtualenv build-image

build-image:
	DOCKER_BUILDKIT=0 docker build -f Dockerfile.kitchen -t salt-kitchen:ubuntu-22.04 .

unit_tests:
	.venv/bin/pytest tests/unit/ -v

prepare_extmods:
	test -e _states || ln -s k0s/_states _states

integration_tests: prepare_extmods
	mkdir -p reports
	DOCKER_BUILDKIT=0 bundle exec kitchen test --destroy=always

tests: unit_tests integration_tests

clean:
	bundle exec kitchen destroy
	rm -rf .venv reports
