{%- set config_path = salt['pillar.get']('k0s:config_path', '/etc/k0s/k0s.yaml') %}
{%- set config_dir_parts = config_path.strip('/').split('/')[:-1] %}
{%- set config_dir = '/' ~ (config_dir_parts | join('/')) %}
{%- set config_spec = salt['pillar.get']('k0s:config:spec', none) %}

include:
  - k0s.install

k0s_config_directory:
  file.directory:
    - name: {{ config_dir }}
    - user: root
    - group: root
    - mode: '0755'

{%- if config_spec is none %}
k0s_config_create:
  cmd.run:
    - name: /usr/local/bin/k0s config create > {{ config_path }}
    - creates: {{ config_path }}
    - require:
      - file: k0s_config_directory
      - file: k0s_binary_install
    - watch_in:
      - test: k0s_service

k0s_config_file:
  file.managed:
    - name: {{ config_path }}
    - create: False
    - replace: False
    - user: root
    - group: root
    - mode: '0600'
    - require:
      - cmd: k0s_config_create
    - watch_in:
      - test: k0s_service
{%- else %}
k0s_config_file:
  file.managed:
    - name: {{ config_path }}
    - source: salt://k0s/files/k0s.yaml.j2
    - template: jinja
    - user: root
    - group: root
    - mode: '0600'
    - require:
      - file: k0s_config_directory
    - watch_in:
      - test: k0s_service
{%- endif %}
