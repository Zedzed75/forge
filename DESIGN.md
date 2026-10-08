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
      bucket: terraform-states
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

| Legacy field | Origin | Target in `forge.yml` |
|---|---|---|
| `project_name` | ansible | `service.name` |
| `description`, `author` | ansible | `service.description`, `service.owner` |
| `environments[].name` | ansible | `service.environments[].name` |
| `environments[].hosts` | ansible | `ansible.hosts.<env>` |
| `environments[].group_vars` | ansible | `ansible.group_vars.<env>` |
| `groups`, `roles`, `options`, `os_family`, `remote_user`, `become`, `ssh_port`, `python_interpreter` | ansible | `ansible:` section, identical |
| `spec_version` | ansible | `forge_version` (unified) |
| `app.name` | helm | `service.name` |
| `app.description`, `app.maintainer_*` | helm | `service.description`, `service.owner`, `service.owner_email` |
| `app.chart_version`, `app.app_version` | helm | `helm.chart_version`, `helm.app_version` |
| `environments[].name` | helm | `service.environments[].name` |
| `environments[].namespace`, `.log_level`, `.components`, `.extra_values` | helm | `helm.environments.<env>` (overrides) |
| `kubernetes`, `layout`, `namespace_strategy`, `create_namespace`, `image`, `components`, `secrets`, `extras` | helm | `helm:` section, identical |
| `schema_version` | helm | `forge_version` (unified) |

Converter: **not needed in production** (no legacy `forge.yml` exists outside
the original repositories), but a **test** helper `tests/legacy_spec.py` will
convert the 5 ansible specs and the 2 helm specs to feed the parity snapshots of
phases 3 and 4.

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

> The eight questions have been settled. Q1, Q5, Q6 and Q7 by an explicit
> answer; Q2, Q3, Q4 and Q8 kept as recommended, without objection. This section
> is from now on a record of decisions: do not reopen it without a new reason.
> Q9 is one, which appeared in production on 2026-09-24 and was arbitrated the
> same day; Q10 is another, opened on 2026-10-08. They are added after the eight
> and reopen none of them.
>
> These `Q` entries are the **technical** arbitrations of the architecture. The
> project's standing **policy** decisions — naming, language, what engineering may
> merge without a card — are numbered `D1`, `D2`, … and live in `DECISIONS.md`.

**Q1. Delimiters of the Ansible templates.** The legacy uses `{{ }}` plus
`j()`/`jstr()` helpers and 6 `{% raw %}` blocks to emit Jinja destined for
Ansible. A single `copier.yml` imposes a single set of delimiters.
→ **DECISION: `[[ ]]` for all the plugins.** The Ansible templates then write
`{{ my_variable }}` literally, `j()`/`jstr()` and the `{% raw %}` disappear. A
clear simplification, at the price of a mechanical conversion of the 51
templates in phase 3. *(Alternative: one template repository per plugin, hence
several `copier.yml` — but then no single `_subdirectory` and a heavier
per-plugin update mechanism.)*

**Q2. Template location and `copier update`.** Verified: a `src_path` pointing
at a subdirectory of a git repository is not recognised as a versioned template
→ update impossible.
→ **DECISION: a single `copier.yml` at the forge repository root, with
`_subdirectory` supplied as data.** Validated end to end (copy + update + merge
of a manual edit).
→ **Still in force. Q2-bis adds the installed case it did not cover.**

**Q2-bis. The template root has two shapes, and the repository one wins.**
*(Reopens Q2 — new reason: forge is being published.)* Q2 answered "where does the
template live" for a checkout and, without saying so, made that the only answer.
The repository root does not exist in a wheel, so a `pip install`ed forge found no
`copier.yml`, and `forge generate` refused to generate anything at all. forge had
never been usable from an install. No test saw it: every test runs from a
checkout, where the repository root is there by construction.

The constraint Q2 measured is what makes this awkward. copier treats `src_path` as
a versioned template only when it is the **exact** root of a git repository, and
only a versioned template can be `copier update`d. So the two requirements pull
apart:

- `copier update` from a checkout needs the root to be the **repository root**;
- generating from an install needs the root to be **inside the distribution**,
  and `site-packages/forge` is the root of no repository.

Both were considered. Putting the root inside the package for everyone is the
smaller change and gives one path instead of two — but it takes `copier update`
and the `_commit` line away from *checkout* users as well, not just installed
ones, since `<repo>/src/forge` is no more a repository root than
`site-packages/forge` is. That was judged too expensive: `forge update` is the
reason rendering goes through copier at all.

→ **DECISION: `template_root()` tries the repository root first, then the package
directory.** A checkout and an editable install take branch one and behave
**exactly as before** — versioned template, `vcs_ref="HEAD"`, `_commit` recorded,
`copier update` working, byte-identical output. A wheel install takes branch two.
`copier.yml` and `partials/` stay at the repository root, the one source of truth,
and are **copied into the package at build time** (`force-include` in
`pyproject.toml`) so that both shapes carry them at `<root>/copier.yml` and
`<root>/partials/`. That is what keeps the templates' `partials/header.jinja`
import working unchanged in both: copier roots its Jinja loader at `src_path`.

Two consequences follow, and both are narrow:

1. **A plugin's `template_subdir` is one prefix longer in a checkout than in an
   install** (`src/forge/plugins/ansible/template` against
   `plugins/ansible/template`). Plugins declare the repository form — the one a
   contributor can see on disk — and the core shortens it
   (`copier_runner.resolve_subdir`) by trying both and keeping the one that
   exists. Resolving by probing rather than by remembering which branch was taken
   also makes `FORGE_TEMPLATE_SRC` accept either shape.
2. **An installed forge cannot `copier update`**, and neither can an install-shaped
   `FORGE_TEMPLATE_SRC`. This is copier's constraint, not a gap in forge:
   `site-packages/forge` has no git history to compare against. `run_update`
   refuses with a message that names the *template* root and points at
   `forge generate --force` or at a git clone — copier's own message says
   "git-tracked template" without indicating which of the two repositories it
   means. For the same reason an installed forge records no `_commit` in
   `.copier-answers.yml`; a checkout still does.

Verified against a built wheel and a venv that never had the repository:
`forge/copier.yml` and `forge/partials/header.jinja` are shipped, and
`forge generate` produces a tree identical to the golden one. Both are asserted on
every run by `tests/test_cli.py::test_the_wheel_ships_the_whole_template_root` and
`::test_an_installed_forge_generates_the_same_project_as_a_checkout` — the second
being the only test in the suite that exercises forge the way a user who ran
`pip install` does.

**Q3. Shape of the data passed to copier.** Three declared questions (`plugin`,
`service`, `domain`, plus `template_subdir` and `forge_version`) rather than one
question per business field.
→ **DECISION: the five-key shape.** Only the declared questions survive the
update; a single `domain` dict avoids duplicating the pydantic schema in
`copier.yml`, at the price of a more verbose `.copier-answers.yml` (readable,
versioned, and that is precisely what we want to re-read).

**Q4. Cross-domain checks.** Two options: rules written in the core (which would
then become domain-dependent), or projections declared by the plugins and
compared by the core.
→ **DECISION: `forge_projection` + generic comparison**, with
`forge_consistency` as the escape hatch. The core stays agnostic, and a third
plugin (Terraform…) inherits the checks without touching the core.

**Q5. Legacy spec converter.** No legacy `forge.yml` exists outside the original
repositories (5 ansible specs + 2 helm specs, all in `tests/`).
→ **DECISION: no `forge import` command shipped.** Confirmed: no legacy
`forge.yml` exists outside the original repositories. A test helper
(`tests/legacy_spec.py`) converts the 7 specs to feed the parity snapshots of
phases 3 and 4.

**Q6. Repository-level files** (`README.md`, `Makefile`, `.gitignore`,
`.gitattributes` at the root of the target). The helm legacy generates them from
its `project/` template; in a monorepo they belong to no domain.
→ **DECISION: the core writes a non-domain minimum** (`forge.yml`, a `README.md`
listing the domains, `.gitattributes`); the helm `Makefile` and the Ansible
`.gitignore` stay **in their domain subdirectory** (`helm/Makefile`), which keeps
every domain self-contained and deletable.

> **Consequences observed in phase 2** — these three files are the only ones
> forge writes without going through copier, which is an assumed exception to the
> "rendering always goes through copier" rule:
> - they are not tracked by `copier update`, so `forge update` does not refresh
>   them; it is `forge generate` that brings them up to date;
> - `forge diff` therefore compares them **explicitly** (`(root)` heading), so as
>   never to announce "up to date" about something it would not have looked at;
> - the target's `forge.yml` is the **hand-edited source of truth**: when the
>   specification read *is* the target's own, it is not rewritten, since
>   re-serialising it would destroy the team's comments;
> - `README.md` and `.gitattributes` obey the same rule as the domain files: no
>   overwriting of a modified file without `--force`;
> - the index lists the domains **of the specification**, never those of the last
>   `--only`: a `forge generate --only ansible` must not make `helm/` disappear
>   from the README of a project where the `helm:` section still exists.

**Q7. Validation under Windows.** Finding: neither ansible-core, nor
ansible-lint, nor helm, nor kubeconform are installed on the Windows side; helm
4.2.4 and kubeconform 0.8.0 are present in WSL Debian; ansible-lint is installed
nowhere.
→ **DECISION: core runner with a WSL fallback** (port of
`tests/ansible_tools.py`). **`pipx install ansible-core ansible-lint` in WSL
Debian is on me, at the start of phase 3** (task recorded in PLAN.md); the
GitHub CI (Linux) remains the authority.

**Q8. Managing the repository and the template versions.** `copier update`
compares git references: by default the **latest tag**. In development,
`--ref HEAD` includes the uncommitted templates (verified).
→ **DECISION: `--ref HEAD` by default** (the render follows the working tree,
and so do the golden tests), `vX.Y.Z` tags placed at each phase to offer stable
update points to the generated projects.

**Q9. Galaxy collection versions of the generated project** — *a question opened
after the fact, arbitrated on 2026-09-24.* `requirements.yml` named the
collections without any constraint whatsoever:
`ansible-galaxy collection install -r requirements.yml` installed whatever
Galaxy served that day. forge's CI took the breakage first —
`community.postgresql` 5.0.0 removed `postgresql_set`, and a three-week-old
commit went red — but the same exposure was delivered to every generated
project. "Same specification, same output" says nothing as long as the output
names dependencies without a version.
→ **DECISION: a floor *and* a major ceiling**, allowed once per collection in
`plugins/ansible/catalog/collections.py`.
- **Per collection, never per role.** Two roles that depend on the same
  collection must not be able to contradict each other; a `RoleDefinition`
  therefore names only a collection name. A role naming a collection absent from
  the table breaks the plugin import, not the user's project.
- **The ceiling, and not only the floor.** A floor documents what the templates
  need, but protects against nothing: the breakage always comes from a major
  published *after* generation. *(Alternative rejected: floor only, less upkeep
  for forge, but the incident reproduces itself as-is at the user's, which is
  precisely what we refuse to ship.)*
- **Assumed consequence: forge has to follow the majors.** Without a regular
  version bump, the generated projects grow old. The procedure is the one for the
  tools pinned in `.github/workflows/ci.yml`: raise the version validated in CI,
  raise `max_major`, fix the templates if the major removed something, ship the
  bump in its own commit. A range stays **widenable by the user at their own
  hand**: `requirements.yml` is a file of their project, and the generated header
  says so.
- **The floor is never guessed.** When we know what the templates require, it
  says so (`community.postgresql >= 3.13.0` for `postgresql_alter_system`).
  Otherwise it is the version validated in CI, with the reason written in the
  generated file: forge does not claim to know what it has not tested, and the
  floor comes down the day someone verifies it.

> **Still exposed, outside this decision** — this decision bears only on the
> **collections** named by `requirements.yml`. Two tool installations remain
> without a version in what forge generates: `pip install --upgrade
> ansible-core ansible-lint` in the `.github/workflows/ansible-lint.yml` workflow
> of the Ansible project, and the `plugins/pipeline/tools.py` table, where
> `ansible-core`, `ansible-lint` **and the three collections** are still free and
> where the collection list is copied over. The first pins in three lines; the
> second requires that `pipeline` learn the `ansible` domain's versions without
> importing it — hence a projection, hence a separate decision.

**Q10. forge's own renderer versions** — *a question opened after the fact,
arbitrated on 2026-10-08.* Q9 pinned what the **generated** projects install.
What **forge itself** installs was still free: every entry in `pyproject.toml`
was a floor (`copier>=9.7`, `pydantic>=2.6`, …) with no lockfile anywhere, so
each CI run resolved whatever PyPI served that day — and `uv`, which did the
resolving, was unpinned too (fixed separately, in the commit that precedes this
entry). Two of those floors are not ordinary dependencies: **`copier` and
`jinja2` are the renderer.** They are the one dependency class that can change
generated output with no line of this repository having moved, which is exactly
what CLAUDE.md's *"same spec ⇒ same generated output"*, the golden trees and the
structural fingerprints exist to guarantee. A fingerprint that moves because a
transitive renderer bump landed overnight is a false alarm, and false alarms are
how a signal stops being read. Worse, `jinja2` was not even a declared
dependency: it arrives through `copier` (`jinja2>=3.1.6`), so it floated at two
removes.
→ **DECISION: a lockfile, used by CI; and no ceilings in the published
metadata.** `uv.lock` is committed, `ci.yml` installs with
`uv sync --locked --extra dev`, and the constraints in `pyproject.toml` stay
floors.

- **A lockfile, and not upper bounds.** Bounds were the tempting answer, because
  they look like Q9's *"the ceiling, and not only the floor"*. The analogy
  breaks on who owns the file. Q9's ceiling is written into `requirements.yml`,
  a file **of the user's project**, and the generated header tells them they may
  widen it by hand. `pyproject.toml` is forge's **published** metadata: a
  ceiling there is imposed on everyone who runs `pip install iac-forge`, is
  resolved against *their* dependency set, and cannot be widened by hand at all.
  `copier<10` would make forge the package that blocks someone else's upgrade,
  months after we stopped looking. The same decision, read correctly, lands on
  opposite answers for a generated file and for a published one.
  *(And bounding `jinja2` would have meant declaring a direct dependency on a
  library forge never imports — with the standing risk of pinning a version
  `copier` itself refuses.)*
- **Assumed consequence: forge tests one version and supports a range.** That
  asymmetry is deliberate, and it is worth saying out loud rather than leaving
  it implied: the golden trees and the fingerprints prove determinism **for the
  locked renderer**, not for every version the floors admit. Nothing here checks
  that `copier` 9.7 — the declared floor — still renders these templates. The
  floor states what we believe, the lockfile states what we verified, and they
  are not the same claim.
- **The lockfile needs a bump path, or it is Q9's problem upside down.** A
  pinned renderer that never updates ages exactly the way a pinned action does.
  `.github/dependabot.yml` therefore watches the `uv` ecosystem — which also
  retires the reason that file used to give for watching only `github-actions`.
  A renderer bump then arrives as a reviewable PR, *which may legitimately move
  the fingerprints*; that movement is read and explained, never re-baselined on
  sight (DECISIONS.md, the note at the top). That watcher runs
  `versioning-strategy: lockfile-only`, because its default would rewrite the
  very floors this decision keeps permissive — and the price of that setting is
  that it is weak on transitive packages, `jinja2` among them. The watcher is
  therefore a partial bump path, and `uv lock --upgrade` run by hand is the
  complete one. Written down in `dependabot.yml`, beside the setting.
- **Local development syncs from the lockfile too.** `CONTRIBUTING.md` and the
  README now say `uv sync`, not `uv pip install -e ".[dev]"`. Otherwise a
  contributor reproducing a CI failure is not reproducing CI's renderer, which
  is the one difference that would matter.
- **Rejected: accept the drift and write down why.** Defensible for a resolver.
  Not for the renderer, in a repository whose central promise is that the same
  specification yields the same bytes.

---

## 9. Tree of the forge repository

*Observed after phase 10, and no longer planned.*

```
forge/
├── CLAUDE.md  PLAN.md  MIGRATION.md  DESIGN.md  README.md  CHANGELOG.md
├── CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  LICENSE
├── copier.yml                     # single root template (§5.1); copied into the
├── partials/header.jinja          # wheel under forge/ so an install can render (§8 Q2-bis)
├── pyproject.toml                 # uv, python >=3.11
├── .gitattributes                 # * text=auto eol=lf
├── examples/                      # six specifications, all tested
├── src/forge/
│   ├── cli.py  errors.py  jinja_ext.py  pipeline.py
│   ├── spec/         io.py  service.py  assembly.py  names.py  types.py
│   ├── plugins_api/  hookspecs.py  manager.py  types.py  checks.py
│   ├── interview/    prompter.py  service_flow.py
│   ├── render/       copier_runner.py  scaffold.py  diff.py
│   ├── validate/     runner.py  tools.py  wsl.py  consistency.py
│   └── plugins/
│       ├── demo/        plugin.py  template/        # core tests only
│       ├── ansible/     plugin.py  spec.py  catalog/  interview.py  validators.py  template/
│       ├── helm/        plugin.py  spec.py  catalog/  interview.py  validators.py  template/
│       ├── terraform/   plugin.py  spec.py  catalog/  interview.py  validators.py  template/  hcl.py
│       ├── monitoring/  plugin.py  spec.py  catalog/  interview.py  validators.py  template/  render.py
│       └── pipeline/    plugin.py  spec.py  jobs.py  tools.py  interview.py  validators.py  template/
└── tests/
    ├── specs/  golden/
    ├── conftest.py  scripted_prompter.py  isolated_domain.py  fake_domains/
    └── test_*.py
```

### Divergences from what this document planned

| Addition | Why |
| --- | --- |
| `pipeline.py` | so that `cli.py` carries no logic: the operations are callable without a terminal |
| `interview/service_flow.py`, `render/scaffold.py`, `render/diff.py` | single responsibility, and the 600-line limit |
| `plugins_api/checks.py` | four domains were rewriting the same "unknown environment" check; it only speaks of `service.environments`, so it stays agnostic |
| `plugins/terraform/hcl.py` | `terraform fmt` aligns the `=` of consecutive lines: a template cannot align keys whose length it does not know, the projection can |
| `plugins/monitoring/render.py` | an alert annotation and the annotation expected by its unit test are computed together, otherwise they diverge |
| `plugins/pipeline/jobs.py`, `tools.py` | deriving jobs from a `GenerationContext`, and knowing how to install the tools the commands name — the only table in the project that names binaries |
| `partials/` at the root | macros shared between templates, resolved by copier's Jinja loader. Copied into the package for the wheel (§8 Q2-bis) |

`tests/parity/` existed throughout the port then was removed in phase 10, along
with `_legacy/` (see `MIGRATION.md`, closing section).

600-line-per-file limit (global CLAUDE.md): the largest file in `src/` has 420;
the largest test module, 468.
