{%- set role = salt['pillar.get']('k0s:role', 'single') %}

include:
{%- if role == 'controller' %}
  - k0s.install
  - k0s.config
  - k0s.controller
  - k0s.service
{%- elif role == 'worker' %}
  - k0s.install
  - k0s.worker
  - k0s.service
{%- elif role == 'single' %}
  - k0s.install
  - k0s.config
  - k0s.controller
  - k0s.service
{%- endif %}
