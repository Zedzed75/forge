# The `forge.yml` format

This file was `DESIGN.md` §3 until ZED-236 split it out. ZED-226's split (D18 in
`DECISIONS.md`) had left `DESIGN.md` at 598 lines against the 600-line warning
threshold of `scripts/check_file_sizes.py` — a two-line margin on the one
register still actively edited, so the next paragraph anybody added to it would
have tripped the gate. §3 is the schema reference: the part readers look things
up in rather than read forward, which is the category the three sections of D18
moved for. The section numbers are unchanged, so an existing citation of
"DESIGN.md §3" or "§3.1" resolves here, and `DESIGN.md` §3 is a pointer to this
file.

This file is named in `TRACKED_PROSE` in `scripts/check_file_sizes.py`, so it
caps itself at the same thresholds as the other registers.

---

## 3. `forge.yml` format

One shared `service:` section, one optional section per plugin. An absent domain
is not generated.

```yaml
---
forge_version: 1

# ---------------------------------------------------------------------------
# Shared block: what all the domains must see in the same way.
# ---------------------------------------------------------------------------
service:
  name: shop                      # DNS label: used as project name, chart name and prefix
  description: "Online storefront"
  owner: "Platform Team"
  owner_email: "platform@example.com"
  labels:                         # business labels, picked up by every domain
    app.kubernetes.io/part-of: commerce
    tier: frontend
  environments:                   # order is significant: dev -> staging -> prod
    - name: dev
      domain: dev.example.net     # DNS domain of the environment (optional)
    - name: staging
      domain: staging.example.net
    - name: prod
      domain: example.net
      production: true            # turns on the plugins' hardened profiles

# ---------------------------------------------------------------------------
# Ansible domain
# ---------------------------------------------------------------------------
ansible:
  os_family: debian               # debian | redhat
  remote_user: ansible
  become: true
  ssh_port: 22
  python_interpreter: auto_silent
  options:
    use_vault: true
    write_lint_config: true
    write_ci: false
  groups:
    - name: webservers
      description: "Front-end web servers"
      roles: [common, users, ssh_hardening, firewall, nginx]
    - name: dbservers
      description: "Database servers"
      roles: [common, users, ssh_hardening, firewall, postgresql]
  hosts:                          # per environment, then per group
    dev:
      webservers:
        - {name: web-dev-01, ansible_host: 192.168.56.11}
      dbservers:
        - {name: db-dev-01, ansible_host: 192.168.56.21}
    prod:
      webservers:
        - {name: web-prod-01, ansible_host: 10.0.1.11}
        - {name: web-prod-02, ansible_host: 10.0.1.12}
      dbservers:
        - {name: db-prod-01, ansible_host: 10.0.2.11}
  roles:                          # role options; completed by the catalogue defaults
    - name: nginx
      options:
        nginx_server_name: shop.example.net
        nginx_document_root: /var/www/shop

# ---------------------------------------------------------------------------
# Helm domain
# ---------------------------------------------------------------------------
helm:
  kubernetes:
    version: "1.31"
  layout: single                  # single | umbrella
  namespace_strategy: per_env     # single | per_env | custom
  create_namespace: false
  image:
    registry: docker.io
    repository: acme/shop
    strategy: appVersion          # appVersion | per_env | fixed
    pull_policy: IfNotPresent
  components:
    - name: api
      kind: deployment
      addons: [service, ingress, configmap, hpa, pdb, serviceaccount]
      port: 8080
    - name: worker
      kind: deployment
      addons: [configmap]
  secrets:
    strategy: placeholder         # never a real value generated
  extras:
    makefile: true
    helm_tests: true

# ---------------------------------------------------------------------------
# Terraform domain (phase 7)
# ---------------------------------------------------------------------------
# The foundation the other domains sit on: the partitioning, its budget, the
# identity that deploys into it. Not the application workload — that is Helm.
terraform:
  terraform_version: "~> 1.9"     # a constraint, never a bare version
  namespace_strategy: per_env     # same | per_env | custom
  resources:                      # selected families; the rest is not generated
    - namespace
    - quota
    - service_account
  backend:
    kind: s3                      # local | s3 | gcs | azurerm | http
    config:                       # no secret key: the model refuses them
      bucket: terraform-state
      region: eu-west-3
  kubernetes:
    auth: kubeconfig              # kubeconfig | in_cluster
    context_per_environment: true
  environments:
    prod:
      kube_context: prod-eu-west-3
      quota: { cpu: "16", memory: 32Gi, pods: 120 }
  extras:
    makefile: true
    tflint_config: true
```

```yaml
# ---------------------------------------------------------------------------
# monitoring domain (phase 9)
# ---------------------------------------------------------------------------
# A self-contained domain: it reads no other section. What it watches is
# declared here, and consistency with the other domains goes through facets.
monitoring:
  scrape:
    interval: 30s                 # the timeout must stay under the interval
    timeout: 10s
    metrics_path: /metrics
  metrics:                        # names specific to the client library
    requests_total: http_requests_total
    request_duration_seconds: http_request_duration_seconds
    status_label: status
  rules:                          # selected families; the rest is not generated
    - availability
    - error_rate
    - probe
  environments:
    prod:
      namespace: storefront-prod
      targets: ["api-1.example.net:9090"]
      probe_urls: ["https://storefront.example.net"]
      thresholds: { error_rate: 0.02, certificate_days: 30 }
  extras:
    makefile: true
    dashboard: true
```

One scrape configuration and one rule set **per environment**: the thresholds
differ, and so does the observed namespace. Every alerting rule is delivered
with the unit test that proves it fires — that is not an option.

```yaml
# ---------------------------------------------------------------------------
# pipeline domain (phase 8)
# ---------------------------------------------------------------------------
# The only domain whose output depends on the OTHER sections, and the only one
# whose output is the repository root: a CI file exists only where the tool
# that reads it looks.
pipeline:
  provider: github              # github | gitlab
  runner: ""                    # empty: default specific to the chosen tool
  trigger:
    branches: [main]
    on_pull_request: true
  build:                        # absent: no build job
    context: .
    dockerfile: Dockerfile
    registry: ghcr.io
    image: acme/storefront
  deploy:                       # absent: the pipeline limits itself to validating
    environments: [dev, prod]   # empty: all of them
    manual_for_production: true
    sequential: true
```

Nothing here says **which domains to validate** or **which commands to run**:
those are the ones the specification asks for, and every domain declares its own
commands (`forge_validators`, `forge_deploy`). The core passes those facts along
through a `GenerationContext`; it schedules nothing.

The state key (`key`, `prefix`) is **not** asked of the specification: it is
derived per environment, so that two roots never write the same state. The
Terraform domain declares the `namespaces` facet, the same one as Helm: that is
where the two domains must agree, and `forge validate` checks it without any
"if terraform then helm" rule existing in the core.

### 3.1 Correspondence with the legacy specs

Moved to `MIGRATION.md` (§ *Correspondence with the legacy specs*) by ZED-226 — it is a record of a `_legacy/` that no longer exists.
