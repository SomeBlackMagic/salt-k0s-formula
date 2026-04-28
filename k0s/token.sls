{%- macro shell_quote(value) -%}'{{ value | string | replace("'", "'\"'\"'") }}'{%- endmacro %}
{%- set token_path = salt['pillar.get']('k0s:token:path', '/etc/k0s/worker-join-token') %}
{%- set token_ttl = salt['pillar.get']('k0s:token:ttl', 24) | int %}
{%- set token_dir = salt['file.dirname'](token_path) %}
{%- set token_path_shell = shell_quote(token_path) %}
{%- set binary = '/usr/local/bin/k0s' %}
{%- if token_ttl == 0 %}
{%- set token_is_current = 'test -s ' ~ token_path_shell %}
{%- else %}
{%- set token_is_current = 'test -s ' ~ token_path_shell ~ ' && test "$(find ' ~ token_path_shell ~ ' -mmin -' ~ (token_ttl * 60) ~ ' 2>/dev/null)"' %}
{%- endif %}

include:
  - k0s.install

k0s_token_directory:
  file.directory:
    - name: {{ token_dir | yaml }}
    - user: root
    - group: root
    - mode: '0755'

k0s_worker_join_token_create:
  cmd.run:
    - name: >-
        umask 077 && {{ binary }} token create --role worker > {{ token_path_shell }}
    - unless: >-
        {{ token_is_current }}
    - require:
      - file: k0s_binary_install
      - file: k0s_token_directory

k0s_worker_join_token_file:
  file.managed:
    - name: {{ token_path | yaml }}
    - user: root
    - group: root
    - mode: '0600'
    - replace: False
    - require:
      - cmd: k0s_worker_join_token_create
