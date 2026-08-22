{%- set _raw_list = salt['pillar.get']('k0s:manifests', []) %}
{%- set _raw_map  = salt['pillar.get']('k0s:manifests_map', {}) %}
{%- set binary = salt['pillar.get']('k0s:binary', '/usr/local/bin/k0s') %}

{# Build base list — copy each entry so we can mutate safely #}
{%- set manifests = [] %}
{%- for item in _raw_list %}
  {%- set entry = {} %}
  {%- do entry.update(item) %}
  {%- do manifests.append(entry) %}
{%- endfor %}

{# Merge map entries into the list: match by name, otherwise append #}
{%- for key, val in _raw_map.items() %}
  {%- set ns = namespace(found=false) %}
  {%- for entry in manifests %}
    {%- if entry.get('name') == key %}
      {%- do entry.update(val) %}
      {%- set ns.found = true %}
    {%- endif %}
  {%- endfor %}
  {%- if not ns.found %}
    {%- set new_entry = {'name': key} %}
    {%- do new_entry.update(val) %}
    {%- do manifests.append(new_entry) %}
  {%- endif %}
{%- endfor %}

{%- for manifest in manifests %}
k0s_manifest_{{ manifest.name | default('manifest_' + loop.index | string) }}:
  k0s_manifest.applied:
    - name: {{ manifest.name | default('manifest-' + loop.index | string) }}
    - binary: {{ binary }}
    {%- if manifest.source is defined %}
    - source: {{ manifest.source }}
    {%- endif %}
    {%- if manifest.content is defined %}
    - content: |
        {{ manifest.content | indent(8, first=False, blank=True) }}
    {%- endif %}
    {%- if manifest.wait is defined %}
    - wait: {{ manifest.wait | tojson }}
    {%- endif %}
{%- endfor %}