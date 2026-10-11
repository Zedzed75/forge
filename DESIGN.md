# DESIGN.md — forge architecture

Phase 1 deliverable. Every statement about copier's behaviour has been
**verified experimentally** (copier 9.17.2); the raw findings are recorded in
`MIGRATION.md` §2. The technical arbitrations are in §8 below; the project's
standing policy decisions (`D1` …) are in `DECISIONS.md`.

---

## 1. Overview

```
forge.yml  ──►  core: loading + validation (pydantic assembled from the plugins)
                  │
                  ├─ for each selected domain ──► forge_answers hook ──► copier.run_copy
                  │        (src = forge repository root, or the package directory
                  │         once installed — §8 Q2-bis;
                  │         _subdirectory = plugin template)
                  │                                          │
                  │                                          ▼
                  │                                  <target>/<domain>/…
                  │                                  + .copier-answers.yml
                  │
                  ├─ forge validate ──► forge_validators hook ──► core runner (subprocess/WSL)
                  ├─ forge validate ──► forge_projection hook  ──► cross-domain checks (core)
                  └─ forge update   ──► copier.run_update per domain
```

The core knows only: specs, a template directory, a data dict, external commands
and projections. It has no notion of SSH, of a role, of a namespace or of a
chart.

---

## 2. Plugin contract (pluggy)

### 2.1 Exchanged types

```python
# forge/plugins_api/types.py

@dataclass(frozen=True)
class DomainInfo:
    """Identity of a generated domain."""
    name: str          # "ansible" — section key in forge.yml and plugin name
    title: str         # "Ansible" — display
    summary: str       # one line, for `forge plugins`
    outdir: str        # output subdirectory, defaults to == name

@dataclass(frozen=True)
class Command:
    """An external validation command declared by a plugin."""
    label: str                       # "helm lint (prod)" — reused as-is in the report
    tool: str                        # binary to locate ("helm", "ansible-lint")
    argv: list[str]                  # arguments, without the binary
    cwd: Path | None = None          # default: the domain's directory
    env: tuple[tuple[str, str], ...] = ()  # environment variables (phase 3, R1)
    stdin_from: str | None = None    # label of a command whose stdout feeds this stdin
    timeout: int = 300
    install_hint: str = ""           # message shown if the binary is absent
    requires_linux: bool = False     # allows the WSL fallback under Windows

@dataclass(frozen=True)
class Issue:
    """A cross-domain validation finding."""
    level: Literal["error", "warning"]
    message: str                     # actionable sentence
    hint: str = ""                   # suggested correction
    domains: tuple[str, ...] = ()    # domains concerned

@dataclass(frozen=True)
class Projection:
    """What a domain claims to have produced, expressed without domain vocabulary.

    The core compares projections with one another: two domains declaring the
    same facet must declare the same value. It is this mechanism — and not
    "if ansible then…" rules — that implements the cross-domain checks.
    """
    service_name: str
    environments: tuple[str, ...]   # the ones the domain MATERIALISES (phase 5),
                                    # not a copy of service.environments
    labels: dict[str, str] = field(default_factory=dict)
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # e.g. ansible → {"inventory_hosts": (...), "groups": (...)}
    #      helm    → {"namespaces": (...), "ingress_hosts": (...)}
    #
    # A facet name belongs to a VOCABULARY SHARED between domains
    # (`forge.validate.consistency.FACET_VOCABULARY`): two domains that use the
    # same name assert that they are talking about the same thing. A facet
    # outside the vocabulary is compared to nobody.
    #
    # Corrected in phase 5: this section proposed `hosts` for both domains,
    # assuming that same name = same meaning. Ansible meant its inventory
    # machines by it, Helm its Ingress hosts — and `forge validate` failed on
    # every two-domain specification. It is the first defect that the meeting
    # of two real domains revealed.
```

### 2.2 Hookspecs

```python
# forge/plugins_api/hookspecs.py
hookspec = pluggy.HookspecMarker("forge")

@hookspec
def forge_domain() -> DomainInfo:
    """Domain identity. The only hook required to be discovered."""

@hookspec
def forge_spec_model() -> type[BaseModel]:
    """Pydantic submodel validating the <domain> section of forge.yml.

    The core assembles the root model from the registered submodels: every
    section is optional, an absent section means "domain not generated". No
    knowledge of the content on the core side.
    """

@hookspec
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conducts the domain's interview and returns its forge.yml section.

    The plugin drives its own questionnaire through the `Prompter` protocol
    provided by the core (text/confirm/select/checkbox/note), never questionary
    directly: that is what makes the interview replayable in tests.
    Returns None if the user declines the domain.
    """

@hookspec
def forge_template_subdir() -> str:
    """Path of the copier template, relative to the forge repository root.

    Example: "src/forge/plugins/ansible/template".
    Passed to copier through `_subdirectory` (see §5). An installed forge renders
    from the package directory, where the same template is one prefix shorter; the
    core shortens it, not the plugin (§8 Q2-bis).
    """

@hookspec
def forge_answers(spec: ForgeSpec) -> dict[str, Any]:
    """Projects the unified spec into the `domain` dict passed to copier.

    Output JSON-serialisable and **deterministic** (fixed key order): it is
    written as-is into `.copier-answers.yml` and replayed by `copier update`.
    """

@hookspec
def forge_validators(spec: ForgeSpec, outdir: Path) -> list[Command]:
    """External commands validating the generated domain, in execution order."""

@hookspec
def forge_projection(spec: ForgeSpec) -> Projection:
    """What the domain claims to produce, for the cross-domain checks."""

@hookspec
def forge_check_spec(spec: ForgeSpec) -> list[Issue]:
    """Cross-checks on the **specification**, before any render.

    A plugin submodel only sees its own section: on its own it cannot verify
    what touches the shared `service:` block. The core calls this hook right
    after assembling the model; an `Issue` at level `error` stops generation, a
    `warning` is displayed and lets it through.

    Added at the phase 4 interface review (arbitration R2): without it, an
    inconsistent specification was generated without flinching and the error
    only came out at the next `forge validate`.
    """


@hookspec
def forge_consistency(spec: ForgeSpec, outdirs: dict[str, Path]) -> list[Issue]:
    """Additional plugin-specific checks (escape hatch).

    The only hook called on **all** the plugins at once; the results are
    concatenated. To be used only for what `forge_projection` cannot say.
    """

@hookspec
def forge_catalog() -> list[CatalogEntry] | None:
    """Catalogue browsable through `forge catalog <domain>` (optional)."""
```

### 2.3 Calling the hooks — a pluggy gotcha

`pm.hook.forge_answers(...)` calls **all** the plugins and returns a list. But
forge needs to address **one** domain at a time. The core therefore wraps
`pm.subset_hook_caller()` in a façade:

```python
manager.domains()            # -> list[DomainInfo], sorted by name (determinism)
manager.domain("ansible")    # -> DomainHooks: .spec_model() .answers(spec) .validators(...) …
```

No `firstresult=True` on the domain-specific hooks: they would be silently
captured by the first registered plugin. Only `forge_consistency` is consumed in
"all the plugins" mode.

### 2.4 Registration

Phase 2: the internal plugins (`demo`, then `ansible`, `helm`) are registered
hard-coded in `forge/plugins_api/manager.py`. Discovery through entry points
(`pm.load_setuptools_entrypoints("forge")`) is added later without changing the
contract. **Adding a domain must not touch any core file** other than that
registration list.

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

---

## 4. Generated tree (two-domain monorepo)

```
<target>/
├── forge.yml                    # copy of the spec (replayability) — written by the core
├── README.md                    # domain index — written by the core (see §8 Q6)
├── .gitattributes               # eol=lf, indispensable to the golden comparisons
├── ansible/
│   ├── .copier-answers.yml      # _commit, _src_path, plugin, service, domain
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── inventories/<env>/hosts.yml
│   ├── inventories/<env>/group_vars/{all,<group>}.yml
│   ├── inventories/<env>/host_vars/<host>.yml
│   ├── group_vars/<group>.yml
│   ├── playbooks/{site,ping,<group>}.yml
│   └── roles/<role>/{tasks,handlers,defaults,vars,meta,templates,README.md}
└── helm/
    ├── .copier-answers.yml
    ├── Makefile
    └── charts/<service>/
        ├── Chart.yaml, values.yaml, values-<env>.yaml, README.md, .helmignore
        └── templates/{_helpers.tpl, NOTES.txt, <component>-<resource>.yaml, tests/}
```

Every domain is self-contained: its `.copier-answers.yml` allows it to be
updated on its own (`forge update --only helm`).

---

## 5. Invoking copier

### 5.1 Root `copier.yml` (single, at the forge repository root; copied into the package for the wheel — §8 Q2-bis)

```yaml
_subdirectory: "[[ template_subdir ]]"     # provided by the forge_template_subdir hook
_answers_file: .copier-answers.yml
_templates_suffix: .jinja
_jinja_extensions:
  - forge.jinja_ext.ForgeExtension
_envops:
  block_start_string: "[%"
  block_end_string: "%]"
  variable_start_string: "[["
  variable_end_string: "]]"
  comment_start_string: "[#"
  comment_end_string: "#]"
  trim_blocks: true
  lstrip_blocks: true
  keep_trailing_newline: true

# Declared questions: ONLY the declared questions are recorded in the answers
# file, so only they survive `copier update`.
plugin:          {type: str}
template_subdir: {type: str}
forge_version:   {type: int, default: 1}
service:         {type: json}
domain:          {type: json}
```

A single `copier.yml`, hence a single set of delimiters `[[ ]]` **for all the
plugins** — Ansible included (see §8 Q1). The templates access
`[[ service.name ]]`, `[[ domain.groups ]]`, and so on.

Every plugin template must contain `[[ _copier_conf.answers_file ]].jinja`
(otherwise no answers file is written and the update is impossible).

### 5.2 Generation

```python
run_copy(
    src_path=str(template_root),               # repo root, or the package once installed
    dst_path=str(target / domain.outdir),      # <target>/ansible
    data={
        "plugin": domain.name,
        "template_subdir": hooks.template_subdir(),
        "forge_version": spec.forge_version,
        "service": spec.service.model_dump(mode="json"),
        "domain": hooks.answers(spec),
    },
    defaults=True,      # mandatory: otherwise an interactive prompt -> crash under Git Bash
    unsafe=True,        # required as soon as _jinja_extensions is declared
    quiet=True,
    overwrite=force,
    vcs_ref=ref,        # "HEAD" by default: includes the uncommitted templates
)
```

`template_root` is resolved in this order: `$FORGE_TEMPLATE_SRC`, then the git
root containing `forge/__init__.py`, then the publication URL (installed usage).

Under Windows, the core wraps every copier call with
`GIT_CONFIG_COUNT=1 / GIT_CONFIG_KEY_0=core.longpaths / GIT_CONFIG_VALUE_0=true`:
path names carrying `yield` otherwise go past the limit in copier's temporary
clone.

### 5.3 File multiplicity — the `yield` tag

The legacy `planner.py` disappears in favour of template paths:

```
inventories/[% yield e from domain.envs %][[ e.name ]][% endyield %]/hosts.yml.jinja
inventories/[% yield e from domain.envs %][[ e.name ]][% endyield %]/host_vars/[% yield h from e.hosts %][[ h.name ]][% endyield %].yml.jinja
roles/[% yield r from domain.roles %][[ r.name ]][% endyield %]/tasks/main.yml.jinja
charts/[[ service.name ]]/values-[% yield e from domain.envs %][[ e.name ]][% endyield %].yaml.jinja
```

Rules (verified): a single `yield` tag per path **segment**; nesting possible
between segments, the parent segment's variable staying available; forbidden
inside a file's content; a segment rendered empty deletes the file (`[% if %]`
= file filter).

Consequence for the Ansible roles: the templates common to all the roles
(`meta`, `README`) are written once under a role `yield`; the files specific to
one role (e.g. `firewall/tasks/ufw.yml`) are filtered by
`[% if r.name == 'firewall' %]`, or filed under a conditional subtree.
**Arbitration to be made in phase 3 on a real role before converting the 7.**

### 5.4 `forge update`

```python
# 1. rewrite _src_path (absolute, hence tied to the originating workstation) to template_root
# 2. then:
run_update(dst_path=str(target / domain.outdir),
           defaults=True, overwrite=True, unsafe=True,
           conflict="inline", vcs_ref=ref)
```

Verified: a template evolution is three-way merged into a hand-edited file, both
modifications being preserved. `_commit` moves from one tag to the other.
`--only` restricts to the requested domains.

Prerequisites: the target directory is a git repository (copier requires it for
the merge), and the template must be **committed** if `--ref` designates a tag.

### 5.5 `forge diff`

Rendered into a temporary directory (`run_copy` into a tmpdir, never `pretend`,
which writes nothing), then structurally compared with the target: files added /
removed / modified, and the number of changed lines. Summary only — no full diff
displayed (context economy rule).

---

## 6. Validation

1. **Domain validators**: `forge_validators(spec, outdir) -> list[Command]`, run
   by the core's runner (subprocess, timeout, capture, stdin chaining through
   `stdin_from`, `Report`/`Check` reporting taken over from helm-forge).
2. **Missing tool**: installation message (`install_hint`), no Python traceback.
   Explicit failure exit, or `SKIP` reported if `--skip-missing`.
3. **WSL fallback**: under Windows, a `requires_linux=True` command is relaunched
   through `wsl.exe -d <distro>`, the project being copied outside the Windows
   mount (Ansible refuses a world-writable `ansible.cfg`). Direct port of
   `tests/ansible_tools.py`.
4. **Cross-domain checks** (core, domain-agnostic): comparison of the
   `Projection`s — `service_name` identical everywhere, `environments`
   identical, `labels` not contradictory, then every `facet` declared by at
   least two domains (e.g. `hosts` declared by ansible and by helm through the
   Ingress hosts).
5. **Escape hatch**: `forge_consistency` for what the projections do not
   capture.

---

## 7. CLI surface

| Command | Role |
|---|---|
| `forge new [-o DIR] [--spec-out forge.yml] [--only a,b] [--force] [--dry-run]` | interview (`service:` block by the core, then `forge_interview` per domain), writing of `forge.yml`, generation |
| `forge generate [-s forge.yml] [-o DIR] [--only …] [--ref REF] [--force] [--dry-run]` | regenerates from an existing spec |
| `forge validate [-s forge.yml] [-o DIR] [--only …] [--skip-missing]` | per-domain validators + cross-domain checks |
| `forge update [-o DIR] [--only …] [--ref REF] [--conflict inline\|rej]` | `copier update` per domain |
| `forge diff [-s forge.yml] [-o DIR] [--only …]` | gap between the target and a fresh render (summary) |
| `forge plugins` | registered domains, recognised sections, state of the external tools |
| `forge catalog <domain> [item]` | catalogue provided by the plugin (roles, components) |
| `forge --version` | version |

Common conventions: `--only` accepts a list of domains (explicit error on an
unknown domain), `--dry-run` writes nothing, output is not coloured if
`NO_COLOR` is defined.

---

## 8. Open questions — **arbitrated on 2026-08-23**

The `Q` register moved to [`docs/ARBITRATIONS.md`](docs/ARBITRATIONS.md) (ZED-226, D18). Q1 … Q11 keep their identifiers there, so a citation of "§8 Q2-bis" still resolves.

---

## 9. Tree of the forge repository

Moved to [`docs/REPOSITORY-TREE.md`](docs/REPOSITORY-TREE.md) (ZED-226, D18).
