# forge

Deterministic generator of complete, commented infrastructure projects
(Ansible, Helm, Terraform, monitoring, CI/CD) from a single `forge.yml`
specification.

What forge produces is not a skeleton left to be filled in: every file carries a
header saying what it is for, every exposed variable is commented with its
allowed values, and **the generated project passes the real validators of its
domain** — not an internal check, the actual tools.

## A project does not need everything

One project may need nothing but a Helm chart. Another, nothing but Ansible
roles and playbooks. A third, nothing but a Terraform foundation, or nothing but
alerting rules. **You are the one who chooses**, and forge produces nothing
else.

```bash
forge generate -s examples/helm-only.yml       -o /tmp/storefront  # helm/ only
forge generate -s examples/ansible-only.yml    -o /tmp/gateway     # ansible/ only
forge generate -s examples/terraform-only.yml  -o /tmp/foundation  # terraform/ only
forge generate -s examples/monitoring-only.yml -o /tmp/payment     # monitoring/ only
forge generate -s examples/pipeline-only.yml   -o /tmp/ci          # a CI chain on its own
```

These six examples are committed and tested: see [`examples/`](examples/).

| Domain | Section | Produces | Validated by |
| --- | --- | --- | --- |
| Ansible | `ansible:` | inventories, playbooks, roles | `ansible-playbook --syntax-check`, `ansible-lint` (production profile) |
| Helm | `helm:` | complete chart, per-environment values | `helm lint`, `helm template`, `kubeconform -strict` |
| Terraform | `terraform:` | one module, one root per environment | `terraform fmt`, `init`, `validate`, `tflint` |
| Monitoring | `monitoring:` | collection, alerting rules, **alert tests** | `promtool check config`, `check rules`, `test rules` |
| Pipeline | `pipeline:` | GitHub Actions or GitLab CI chain, at the root | `actionlint` (GitHub), `yamllint` (GitLab) |

Three ways to choose:

| You want | You do |
| --- | --- |
| a single domain | write only its section in `forge.yml` — an absent section generates nothing |
| a restricted run | `forge generate --only helm` |
| to decide at creation time | `forge new` asks which domains to produce |

`--only` always **restricts**, it never adds: asking for a domain the
specification does not declare is a named error, not an empty generation.

`forge plugins -s forge.yml` tells which domains are requested and which are
not; `forge generate --dry-run` announces what it would produce without writing
anything. A specification that declares no domain does not silently produce an
empty project: forge says which ones are available and how to ask for one.

Asking for several domains at once is **one** possible use — forge then checks
that they stay consistent with each other — not the normal one.

## Getting started

```bash
forge new -o my-service     # interview, writes forge.yml, then generates
forge validate -o my-service
```

The interview first asks for the service identity and its environments, then
**which domains to generate**, and afterwards only asks about those.

| Command | Role |
| --- | --- |
| `forge new` | interactive interview — asks which domains to generate — writes `forge.yml` then generates |
| `forge generate` | replays an existing specification |
| `forge validate` | each domain's validators + cross-domain consistency |
| `forge update` | applies template evolutions without overwriting your changes (needs a git-tracked template — see below) |
| `forge diff` | summarises the gap between the target and a fresh render |
| `forge plugins` | registered domains and state of the external tools |
| `forge catalog <domain>` | catalogue published by a plugin, pitfalls included |

`forge catalog <domain> <item>` is more than a list: every resource family
documents its **measured pitfalls** there — why a ResourceQuota breaks a chart
that does not declare its `requests`, why a NetworkPolicy without a DNS opening
cuts off all name resolution, why a `+Inf` bucket makes a quantile lie.

## Architecture

### The core knows no domain

`src/forge/` knows how to load a specification, call copier, run commands and
compare projections. It does not know what a namespace, a role or a histogram
is. All domain knowledge lives in `src/forge/plugins/<domain>/`.

This separation is not decorative: **adding a domain costs one line of the
core** — the `BUILTIN_PLUGINS` entry. It is checked on every addition, and the
last two domains confirmed it.

```
src/forge/
├── spec/           # shared `service:` block, assembly of the root model
├── plugins_api/    # the contract: hookspecs, exchanged types, registry
├── render/         # copier invocation, repository-level files, diff
├── validate/       # command execution, WSL bridge, cross-domain checks
├── interview/      # input protocol, replayable in tests
├── pipeline.py     # chaining of the operations, no terminal
├── cli.py          # argument reading and display, nothing else
└── plugins/        # ansible/ helm/ terraform/ monitoring/ pipeline/  (+ demo/, not for production)
```

### What copier does, and why

Rendering **always** goes through copier, never through a hardcoded file write.
That is what makes `forge update` possible: a project delivered six months ago
receives the template evolutions without losing the settings made by hand.

`forge update` is the one command with a condition `forge generate` does not have:
copier merges by comparing two git references, and for that it needs the template
to be a git repository. From a checkout it is, and `forge update` works. An
installed forge renders from `site-packages/forge/`, which has no git history — so
it says so and points at `forge generate --force`, or at
`FORGE_TEMPLATE_SRC=<a git clone of this repository>` if you want the merge.
DESIGN.md §8 Q2-bis has the reasoning.

Consequence for the templates: they use the `[[ ]]`, `[% %]` and `[# #]`
delimiters, never `{{ }}`. Helm and Ansible both write `{{ ... }}` in their own
files; with the default delimiters, every template would have required a `raw`
block. Here, `{{ .Values.image.tag }}` goes through the render untouched.

### How two domains meet without knowing each other

No plugin reads another's section. When two domains have to agree, they declare
a **facet** — a fact, in a shared vocabulary — and the core compares:

| Facet | What it designates | Declared by |
| --- | --- | --- |
| `namespaces` | partitions where the service lives | terraform, helm, monitoring |
| `ingress_hosts` | names by which the service is reachable from outside | helm, monitoring |
| `inventory_hosts` | machines named in an inventory | ansible |
| `groups` | groupings of machines sharing a role | ansible |

Terraform creates the namespace, Helm deploys into it, monitoring watches it: if
the three stop naming it the same way, `forge validate` says so — without any
"if terraform then helm" rule existing anywhere.

The vocabulary is **closed**: the core only compares the facets listed in it. A
facet outside the vocabulary is harmless, but has no effect. The rule comes from
a real false positive: Ansible and Helm both declared `hosts`, for unrelated
things.

### The domain that federates the others without knowing them

The `pipeline` domain is the only one whose output **depends on the other
sections**. It generates one validation job per declared domain, with the
commands each domain announces itself and the installation of the tools they
require. Adding a section to `forge.yml` adds a job, without a line of template
changing.

The core does not become a scheduler for all that: it assembles a
`GenerationContext` from hooks it was already calling — `DomainInfo`, `Command`,
`Projection` — and draws no conclusion from it. The `pipeline` plugin contains no
domain name; a fake domain it has never seen gets its job, and a test proves it.

Three translations call for care there, and each is locked down by a test:

- **chaining through stdin** becomes a redirection through a file, never a pipe:
  `pipefail` does not exist in the `/bin/sh` of a Debian image, and a pipe there
  would mask the failure of the source command;
- **the deployment order** follows `DomainInfo.deploy_order`, not the alphabet —
  otherwise the chart would go out before the Terraform that creates its
  namespace;
- **local environment variables** are discarded: a cache path computed on the
  workstation makes no sense on a runner, and carving it in would make the
  output depend on the machine that generated it.

A domain that does not declare how to deploy itself is **named** in the
generated file, never guessed. Likewise for a tool the installation table does
not know: the step fails naming it, rather than letting the job fall over
further down on a "command not found".

## Writing a domain plugin

A plugin is a Python module exposing `@hookimpl`s. Exactly one hook is
mandatory.

| Hook | Mandatory | Role |
| --- | --- | --- |
| `forge_domain()` | **yes** | the domain's identity: name, title, summary, output directory |
| `forge_spec_model()` | yes in practice | pydantic submodel validating the `<domain>:` section |
| `forge_template_subdir()` | yes in practice | path to the copier template |
| `forge_answers(spec, context)` | yes in practice | projects the spec into the `domain` dict the templates read; `context` describes the other requested domains, and a plugin that does not need it does not declare the parameter |
| `forge_check_spec(spec)` | no | checks the submodel cannot do — it does not see `service:` |
| `forge_validators(spec, outdir)` | no | external commands validating the generated project |
| `forge_deploy(spec, outdir, env)` | no | how this domain deploys. The core **never** runs it: these commands exist only to be written into a pipeline |
| `forge_projection(spec)` | no | what the domain claims to produce, for the facet comparison |
| `forge_interview(prompter, service)` | no | `forge new` questionnaire |
| `forge_catalog()` | no | catalogue browsable by `forge catalog` |
| `forge_consistency(spec, outdirs)` | no | escape hatch: checks on the **already written** project |

### The procedure to follow

1. **`spec.py`** — a pydantic model inheriting from `ForgeModel` (`extra="forbid"`:
   an unknown key is a typo, never a silence). Reject early whatever would only
   show up late: a version constraint without an upper bound, a backend without
   its mandatory key, a scrape timeout greater than its interval.
2. **`catalog/`** — the families of what the domain knows how to produce, with
   their pitfalls. That is the domain knowledge; the rest is only plumbing.
3. **`derive.py` / `answers.py`** — the projection into the `domain` dict. It
   must be **JSON-serialisable and deterministic**: it is written as-is into
   `.copier-answers.yml` and replayed by `copier update`. No pydantic object, no
   `set`, no absolute path.
4. **`template/`** — the templates, `[[ ]]` delimiters.
5. **`tree.py`** — the list of produced paths, so that the generated README does
   not lie. A test confronts it with the real render.
6. **`validators.py`** — the real commands. A domain whose output nothing checks
   is not finished.
7. One line in `BUILTIN_PLUGINS`, a reference specification in `tests/specs/`,
   a single-domain example in `examples/`.

### Three pitfalls that have bitten

- **Never read a key in dotted notation when it bears the name of a dict
  method.** In Jinja, `object.values` resolves the method before the key, and the
  template writes `<built-in method values...>` into the generated file. The safe
  form is `object["values"]`. Two tests enforce it, one on the template sources,
  the other on the output.
- **Keep template names short.** Windows caps a path at 260 characters, and
  copier clones the repository into a temporary directory before rendering. A
  name carrying two explicit `yield` tags goes past the limit; use short name
  lists and re-read the full entry in the body of the file.
- **Never write into a generated file a value read from the process
  environment.** A cache path computed on the development workstation makes the
  output machine-dependent, and the golden test can no longer compare.

### The slots pattern

A template specific to an item exists without a `[% if %]` appearing in its
path: the projection exposes a `{key: [item] or []}` dict, and copier's `yield`
tag decides whether to write it. The four domains invented it separately; it has
become a convention.

## What guarantees the output

**Same specification, same output, byte for byte.** Golden tests compare every
render to a committed reference. They catch an intended change just as well as
an accidental non-determinism.

**The generated project passes the real validators of its domain.** The five
reference specifications trigger **31 external commands**, launched by the test
suite on genuinely rendered projects. These are not internal checks: they are the
tools the user will run.

One case deserves to be highlighted: the monitoring domain delivers, with every
alerting rule, the **unit test** that proves it fires — `promtool test rules`
builds a synthetic time series and checks that the alert appears with the right
labels. It is the only validator in the project that checks something semantic:
an alerting rule can be syntactically impeccable and stay mute forever.

On Windows, the tools that do not exist natively are looked up in a WSL
distribution. The Linux CI is authoritative.

## Where forge comes from

forge is the port of two standalone generators, `ansible-forge` and `helm-forge`,
which shared a specification model, a Jinja engine, a golden test harness and a
CLI — in duplicate.

The port was carried out at **byte parity**, against frozen snapshots of the
original output: 313 files on the Ansible side, 32 on the Helm side. That parity
served throughout the port, then was removed, along with the original code, once
it was measuring a resemblance to tools that no longer exist — and once the
generated project had outgrown it. The Helm chart has nine resource families the
original tool never had; the Ansible project passes `ansible-lint` in production
profile, which the original suite had never checked.

`MIGRATION.md` keeps the complete record: the merged duplicates, the arbitrations
made, and the assumed divergences.

## Installation and tests

```bash
uv venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
```

On Linux and macOS, replace `.venv/Scripts/python.exe` with `.venv/bin/python`.
If `uv` is not on the PATH, it installs with `python -m pip install uv` and is
then invoked as `python -m uv`.

```bash
.venv/Scripts/python.exe -m pytest                        # everything
.venv/Scripts/python.exe -m pytest -m "not integration"   # without the external tools
```

The tests marked `integration` launch the real validators and skip themselves if
the tool is absent — natively as well as in WSL. CI installs them all: a green
suite there therefore means the generated projects are valid.

The golden references are regenerated with `pytest --regen-golden`, to be done
only after establishing that the gap is intended: the command **ratifies** the
current output, it does not verify it.

One test is skipped as long as the repository carries uncommitted changes:
`copier update` compares two git references, and a render made from a dirty
working tree refers to a temporary commit that cannot be found afterwards.

## Documents

| File | Contents |
| --- | --- |
| `CHANGELOG.md` | what changed in generated output, and what `forge update` asks of you |
| `DESIGN.md` | detailed architecture, plugin contract, arbitrated decisions |
| `MIGRATION.md` | port record: merged duplicates, arbitrations, divergences |
| `PLAN.md` | progress phase by phase, and what each one established |
| `examples/` | six commented specifications, all generated by the test suite |
