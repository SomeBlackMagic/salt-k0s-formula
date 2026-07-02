{%- set _raw_manifests = salt['pillar.get']('k0s:manifests', []) %}
{%- set binary = salt['pillar.get']('k0s:binary', '/usr/local/bin/k0s') %}

{%- if _raw_manifests is mapping %}
  {%- set manifests = [] %}
  {%- for key, val in _raw_manifests.items() %}
    {%- set entry = {} %}
    {%- do entry.update(val) %}
    {%- do entry.update({'name': key}) %}
    {%- do manifests.append(entry) %}
  {%- endfor %}
{%- else %}
  {%- set manifests = _raw_manifests %}
{%- endif %}

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