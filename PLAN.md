# PLAN — forge

Memory between sessions. One phase per session: read this file, handle ONE phase,
update the "Current state" section, commit, stop.

## Phases

- [x] **Phase 0 — Bootstrap**: git repository, `_legacy/ansible-forge/`, `_legacy/helm-forge/`,
      `CLAUDE.md`, `PLAN.md`.
- [x] **Phase 1 — Audit and design** (no production code)
  - [x] Selective audit of `_legacy/` -> `MIGRATION.md` (keep / adapt / discard per artefact,
        maturity of each tool, Jinja2 delimiters, conflicts with copier).
  - [x] Design -> `DESIGN.md`: pluggy hookspec, `forge.yml` schema, generated tree,
        copier invocation per plugin, CLI surface, open questions.
  - [x] **Human validation obtained (2026-08-23)**: Q1 `[[ ]]` everywhere, Q5 no
        external legacy spec (test helper only), Q6 minimal core + the rest per
        domain, Q7 installing ansible-core/ansible-lint in WSL is on me.
        Q2, Q3, Q4, Q8 kept as recommended, without objection.
        Complete record: `DESIGN.md` §8.
- [x] **Phase 2 — Core** (2026-08-23)
  - [x] uv scaffolding: `pyproject.toml`, `src/forge/`, `src/forge/plugins/`, `tests/`.
  - [x] Loading/validating the spec assembled from the plugin submodels.
  - [x] pluggy manager + validated hookspec.
  - [x] copier wrapper (run_copy / run_update) + single root `copier.yml`.
  - [x] Validator runner (subprocess, clear errors, missing tool handled cleanly).
  - [x] CLI verbs wired end to end with an internal `demo` plugin (tests only).
  - [x] Golden test harness (`tests/specs/` -> `tests/golden/`, `pytest --regen-golden`).
  - [x] Unit tests: spec assembly, plugin registration.
  - [x] Bonus: cross-domain checks, `forge diff`, WSL bridge, GitHub CI for the core.
- [x] **Phase 3 — Porting the Ansible plugin** (2026-08-25)
  - [x] ansible-core 2.21.3 + ansible-lint 26.8.0 in WSL Debian (decision Q7),
        under `/opt/forge-venv`, with the Galaxy collections under `/opt/forge-collections`.
  - [x] Parity snapshot: 319 files, 6 cases -> `tests/parity/ansible/`.
  - [x] Port of templates / spec submodel / validators / tests according to MIGRATION.md.
  - [x] Complete role catalogue: the 7 roles ported, data identical to the legacy.
  - [x] Golden spec (`ansible-ci.yml`) covering `write_ci`, which parity did not cover.
  - [x] MIGRATION.md and PLAN.md updated, commit.
- [x] **Phase 4 — Porting the Helm plugin** (2026-08-25)
  - [x] Parity snapshot: 32 files, 2 cases -> `tests/parity/helm/`.
  - [x] Port of templates, submodel, validators, interview, tests.
  - [x] **Complete** component catalogue: the 13 families, including the 9 created
        (ingress, configmap, statefulset, cronjob, secret, hpa, pdb,
        serviceaccount+RBAC, networkpolicy).
  - [x] **Interface review: arbitrated (2026-08-25).** R2 -> new hook
        `forge_check_spec`, called before any render; R3 -> `tree.py` stays with the
        plugin, kept up to date by a mandatory test in every domain.
        R1, R4, R5, R6, R7 ratified and documented.
- [x] **Phase 5 — Cross-domain value** (2026-08-25)
  - [x] Consistency checks, with actionable messages. **One false positive
        corrected**: the two domains declared a `hosts` facet that did not
        designate the same thing, and `forge validate` failed on a perfectly
        consistent specification.
  - [x] **Shared facet vocabulary** (`FACET_VOCABULARY`): a facet name is a
        namespace common to all the plugins.
  - [x] `Projection.environments` now carries what the domain **materialises**,
        and not a copy of `service.environments`: an environment deployed by one
        domain and ignored by the other becomes visible.
  - [x] `forge update --only` and `forge diff` per domain, tested on two domains.
  - [x] `two-domains.yml` specification + golden, and an integration test running
        the **nine** real validators of the two toolchains.
- [x] **Phase 6 — The choice of domains, made explicit** (2026-08-25)
  - [x] `CLAUDE.md` carries the **complete** target tree from the brief (five
        plugins) and the rule "the domains are a choice, never a package".
  - [x] README: a dedicated section on the three ways to choose.
  - [x] CLI: `forge generate` announces what it is going to produce before writing;
        an actionable message when no domain is requested; `forge plugins`
        distinguishes the domains the specification requests from the others.
  - [x] `tests/test_domain_selection.py`: 11 tests locking down the three
        ways to choose, including an interview keeping only one domain.
- [x] **Phase 7 — Terraform plugin** (first domain written from scratch) (2026-08-26)
  - [x] No legacy code to port. Promise kept: **a single line of the core
        changed**, the `BUILTIN_PLUGINS` entry. The rest is in
        `plugins/terraform/`, plus four test expectations that were counting
        domains.
  - [x] Catalogue of **seven families** (`namespace`, `quota`, `registry_secret`,
        `service_account`, `network_policy`, `random_secret`, `tls_certificate`)
        and of their measured pitfalls; `terraform:` submodel; 24 templates;
        interview.
  - [x] Validators: `terraform fmt -check`, `terraform init -backend=false`,
        `terraform validate` per environment, `tflint --recursive`.
  - [x] Golden (`terraform-full`) + an integration test running the **eight**
        real commands. 48 tests added.
  - [x] CI: the validators of the Helm **and** Terraform domains are installed there.
        Helm had never been added (a gap from phase 4): its integration tests
        were silently skipping there.
- [x] **Phase 8 — pipeline plugin** (CI/CD) — *parked, then finished*
  - [x] Started, then parked on `phase-8-pipeline` on 2026-08-26 to consolidate
        the production domains first. Resumed afterwards, rebased on
        `master`, tested and finished.
  - [x] The domain that federates the others **without knowing them**: it generates a
        validation job per declared domain, with the commands each one
        announces itself. The core assembles a `GenerationContext` from
        existing hooks and draws no conclusion from it.
  - [x] Two dialects — GitHub Actions and GitLab CI — for the same jobs.
  - [x] Validators: `actionlint` (GitHub), `yamllint` (GitLab). The
        asymmetry is assumed and documented: there is no offline GitLab
        linter.
  - [x] Golden on both dialects, 36 tests, including the decisive witness — a
        **fake domain the plugin has never seen** gets its job.
  - [ ] The domain that federates the others: image build, calling the validators
        of every domain present, deployment per environment.
  - [ ] Must read what the other domains declare **without knowing them**:
        it is the first plugin whose output depends on the other sections. To
        be scoped with care — the core must not become a scheduler.
  - [ ] Validators: `actionlint` (GitHub) or the GitLab linter.
- [x] **Phase 9 — monitoring plugin** (2026-08-26)
  - [x] Six rule families (`availability`, `error_rate`, `latency`,
        `saturation`, `restarts`, `probe`), eight alerts, one scrape
        configuration **per environment** — the thresholds and the observed
        namespace differ from one environment to the next.
  - [x] Validators: `promtool check config`, `check rules`, and above all
        **`promtool test rules`**: every alert is delivered with a unit
        test that proves it fires, with the right labels and the
        right annotations. Three commands per environment.
  - [x] **Self-contained** domain: it reads no other section. Its meeting with
        the other domains goes through the facets (`namespaces`,
        `ingress_hosts`), as planned since phase 5.
  - [x] Golden + an integration test running promtool. 66 tests added.
- [x] **Phase 10 — Finishing** (2026-08-26)
  - [x] Critical review. Six pieces of dead code removed after verifying
        that no path reached them, including two error classes never
        raised (`ToolMissingError`, `ValidationFailed`): the core reports a
        missing tool through a **report**, not an exception, and raising would
        have lost the report.
  - [x] Duplication: the "unknown environment" check was rewritten
        identically in four domains. It now lives in
        `plugins_api/checks.py`, which speaks only of `service.environments` —
        hence without adding the slightest domain knowledge to the core.
  - [x] Complete README: architecture, guide to writing a plugin (the ten
        hooks, the procedure to follow, the three pitfalls that have bitten), provenance.
  - [x] `examples/`: five committed specifications, including **four
        single-domain cases**, all generated by the test suite.
  - [x] Parity divergences 12 to 15 lifted **in one block**, snapshot re-blessed in the
        same commit. Two mentions kept and explained: they are names of
        files dropped on the managed machines, renaming them would leave
        the old one in place.
  - [x] Removal of `_legacy/`, of `tests/parity/`, of its two test
        modules and of its harness.

## Current state / next action

**State**: **project delivered, target complete**. The ten phases are finished.
**568 tests collected**, all green, integration included.

The **five** domains of the original brief are delivered and validated by their
real tools: **Ansible**, **Helm**, **Terraform**, **monitoring**, **pipeline**.
Each generates on its own, and that is the normal use case.

The project's promise: **one single description of the service, and you choose
what you get out of it.** A domain absent from `forge.yml` is never generated;
`--only` restricts a run; the interview asks which domains to produce.

The two-domain case (`tests/specs/two-domains.yml`) is **one** possible use,
not the normal use: it serves to prove that two domains stay consistent with
each other when they are requested together. The **nine** external validators of
the two toolchains pass on it (`ansible-playbook --syntax-check` per
environment, `ansible-lint`, `helm lint`, `helm template` and
`kubeconform -strict` per environment), without the core knowing what a role or
a chart is.

The two domains are delivered and registered (`BUILTIN_PLUGINS`): `forge new`,
`forge generate`, `forge validate`, `forge diff` and `forge catalog <domain>`
work end to end on a real Ansible project **and** on a real Helm chart.

Helm: **parity 32/32** with the original generator, **plus nine resource
families created** that the legacy never had. The complete chart passes
`helm lint`, `helm template` on every environment and `kubeconform -strict`.
Five defects were found by the completion itself and corrected
(see `MIGRATION.md` §7) — including a StatefulSet deprived of its headless
Service, which no validator could see.

Ansible: **parity 313/313** on the 6 cases of the snapshot, apart from the
documented divergences (`MIGRATION.md` §7). And beyond parity, the generated
project passes `ansible-playbook --syntax-check` on every environment **and**
`ansible-lint` in the `production` profile — which the legacy suite had never
verified, its one skipped test bearing precisely on that.

What phase 2 had delivered:
- a single root `copier.yml`, `[[ ]]` delimiters, five declared questions.
- `src/forge/`: `spec/` (io, service, types, names, assembly), `plugins_api/`
  (hookspecs, manager, types), `render/` (copier_runner, scaffold, diff),
  `validate/` (tools, wsl, runner, consistency), `interview/`, `jinja_ext.py`,
  `pipeline.py`, `cli.py`.
- The `demo` plugin (`src/forge/plugins/demo/`), **never registered in production**:
  it is loaded through `FORGE_PLUGINS=forge.plugins.demo.plugin` and exercises the
  nested yields, file filtering through `[% if %]`, plugin filters.
- CLI verbs: `new`, `generate`, `validate`, `update`, `diff`, `plugins`,
  `catalog`, `--version`.
- `tests/`: reference specs, blessed goldens, `--regen-golden` harness.
- GitHub CI (3.11/3.12/3.13 matrix); the domain tools are added there in
  phases 3 and 4.

Adversarial review of the core (2026-08-23): 25 real defects confirmed, all
corrected straight away. The five that matter for what follows:
1. **Output normalisation** — the per-line `rstrip` and the collapsing of
   empty lines inherited from the legacy **corrupted** the generated YAML scalars.
   The core now limits itself to `CRLF -> LF` + a trailing newline
   (`MIGRATION.md` §5, box). In phases 3 and 4, a template that leaves
   blanks is corrected **in the template**, never in the core.
2. **Domain names** — a plugin named `service` silently overwrote the
   shared block of the assembled model. `register()` now validates the name
   (lowercase identifier, neither a keyword nor a reserved name of the root model).
3. **`_src_path`** — the rewrite dirtied the target and made `forge update`
   impossible; forge fixes the line then **stops**, asking for the commit.
4. **`stdin_from` chaining** — a non-existent source label produced a
   green "skipped"; it is now a `PluginError`. Important for Helm:
   `kubeconform` reads the output of `helm template` through stdin.
5. **Repository-level files** — written after the render, never overwritten without
   `--force`, the target's `forge.yml` preserved with its comments, index
   computed on the specification and not on `--only`, and compared by
   `forge diff` under the `(root)` heading.

Assumed divergences from `DESIGN.md` §9 (planned tree):
- addition of `pipeline.py` (chaining of the operations) so that `cli.py` carries
  no logic; addition of `interview/service_flow.py`,
  `render/scaffold.py` and `render/diff.py` (SRP, 600-line limit).
- `BUILTIN_PLUGINS` contains `forge.plugins.ansible.plugin` since phase 3.
  Adding Helm in phase 4 = one more line, no other modification of the core:
  that is the promise of DESIGN.md §2.4, kept.

## Interface review — record for human arbitration

`PLAN.md` reserved this review for a human validation, before any 3rd plugin.
**Arbitration rendered on 2026-08-25**: R2 and R3 settled as recommended, the five
other findings ratified. The table stays here as a record of decisions — do not
reopen it without a new reason.

| # | Finding | Recommendation |
|---|---|---|
| R1 | **`Command.env` was added along the way** (phase 3). `DESIGN.md` §2.1 described `Command` without that field. Without it, `ANSIBLE_COLLECTIONS_PATH` was untransmittable and `--syntax-check` failed on modules that `requirements.yml` nevertheless declares; Helm uses it for `KUBECONFORM_SCHEMA_LOCATION`. | **Ratify**: two domains out of two needed it. Bring `DESIGN.md` §2.1 up to date. |
| R2 | **ARBITRATED: hook added.** **The contract had no cross-check at model level.** A plugin submodel only sees its own section: neither Ansible nor Helm can verify on its own that the environments it cites exist in `service.environments`. Both go through `forge_consistency`, which is only called at `forge validate` — **not at `forge generate`**. An inconsistent specification is therefore generated without flinching, and the error only comes out at the next `validate`. | **Add a hook** `forge_check_spec(spec) -> list[Issue]`, called by the core right after assembling the model, hence before any render. `forge_consistency` would remain for what needs the written files. |
| R3 | **ARBITRATED: left to the plugin, with a mandatory test.** **The list of files to write is duplicated in every plugin** (`ansible/tree.py`, `helm/tree.py`). copier cannot say in advance what it is going to produce, and both domains display a tree in their README. A template added without updating `tree.py` makes the README false — a test catches it on the Ansible side, the lesson has been learned twice. | **A core service**: a "dry" render into a tmpdir gives the exact list. The core could expose it to the templates (`domain.tree`) instead of every plugin guessing it again. |
| R4 | **The two plugins invented the same idiom, separately**: `domain.role_slots.<role>` and `domain.component_slots.<family>`, a `{key: [item] or []}` dict that lets a template specific to an item exist without `[% if %]` in the path. | **Document as a pattern** in `DESIGN.md` §5.3. Do not impose it in the core: it is a template convention, not an API. |
| R5 | **`.copier-answers.yml` grows.** It carries the whole `domain` dict: ~23 KB on the richest Ansible case. That is intended (decision Q3: readable, versioned, re-read), but nobody had put a number on it. | **Leave as-is**, and say so in `DESIGN.md` §8 Q3. The alternative — putting only the spec in it — would break `copier update`. |
| R6 | **`DomainInfo.outdir` has never been used**: both domains use the default (`ansible/`, `helm/`). | **Keep**: the field costs one line and a third domain will need it (`terraform/environments/` for example). |
| R7 | **The interview asks the user twice**: the core asks which domains to generate, then the plugin can still decline by returning `None`. Ansible uses it (no group named), Helm too (no component). | **Keep**, but say it in the hookspec: the plugin's `None` does not mean "the user refuses the domain", it means "there is nothing to generate". |

**TARGET CORRECTION (2026-08-25).** The original brief named **five**
plugins — `ansible`, `helm`, `terraform`, `pipeline`, `monitoring` — and
`CLAUDE.md` had reduced them to "Ansible, Helm, more later". The five phases
already done were therefore done against an amputated target. `CLAUDE.md` now
carries the complete target tree; the plan is extended by three domain phases.

Nothing that has been built is called into question: the core is agnostic,
and the three remaining domains are precisely what is going to prove it — none
of them comes from a legacy tool.

**A scoping point to correct too**: the domains are a **choice**, never a
package. The mechanism exists and works (section absent from forge.yml, `--only`,
interview), but the documentation and the CLI make a poor job of showing it.

**Consolidation of 2026-08-26** — refocusing asked for by the user: the tool
must be able to produce *on demand* Terraform, **or** a Helm chart, **or**
Ansible roles. Not every project needs everything, and the choice belongs to
the user. The mechanism existed; what was missing is that it be
**structurally invulnerable to drift** and **visible**.

What was done:
- `tests/test_domain_selection.py` rewritten: **no domain name or count is
  hardcoded any more**. Everything is read from the plugin registry, and
  `test_every_shipped_domain_has_a_single_domain_specification` makes the
  suite fail if a domain is added without its single-domain case. 11 tests -> 34.
- One single-domain case parametrised per domain: generation, real content of the
  target, `forge validate`, `forge diff`, `forge plugins`. Terraform enters it,
  which was not the case.
- `examples/` delivered: `ansible-only.yml`, `helm-only.yml`,
  `terraform-only.yml`, `foundation-and-chart.yml`, and a README explaining the
  three ways to choose. **Every example is generated by the test suite** —
  an outdated example is impossible.
- README refocused: "A project does not need everything", a table of the three
  domains and their validators, at the top of the file.

One behaviour was **discovered** while writing those tests, and locked down:
`--only` on a domain the specification does not declare raises a named error
instead of producing nothing. That is the right behaviour — a silence
would suggest the domain had been generated — but it was tested nowhere.

What phase 9 established:
- **A domain can do without knowing the others.** Monitoring reads
  no neighbouring section: what it watches is declared at home, and
  consistency goes through the facets. It is the useful counter-example to phase 8,
  where the pipeline needed a context provided by the core.
- **`promtool test rules` verifies what no other validator in the project
  verifies: the meaning.** An alerting rule can be syntactically impeccable
  and stay mute forever — a non-existent metric, a misspelled
  label, a comparison on the wrong side of the threshold. The alert unit
  tests are therefore **unconditional**: making them optional invited the
  wrong choice.
- **The test series must follow the thresholds.** promtool found the defect
  on its own: a test quantile at 1.9 s validated a threshold at 1 s and failed on
  a threshold at 2 s. The fixtures are now computed from the threshold, with a
  clear margin, and a test verifies that property.
- **A Jinja pitfall became a tested rule.** A key named `values`
  caused `<built-in method values...>` to be written into a generated file: in
  Jinja, `object.values` resolves the dict method before the key. Two guards
  now cover **all** the domains — one on the template sources,
  the other on the rendered output. The Helm templates already used the safe form
  `c.config["keys"]` without that being written down anywhere.

What phase 10 established:
- **Parity had stopped measuring what matters.** It compared the output to
  tools that no longer exist, while the generated project had outgrown them
  as early as phase 4 — nine unprecedented Helm families, `ansible-lint` in production
  profile. Removing it was the only way not to lie about what the
  suite verifies.
- **The dead-code review found an intention, not only lines.**
  `ToolMissingError` and `ValidationFailed` described a design that was not
  retained: reporting through an exception rather than through a report. Keeping them would
  have suggested they were in use.
- **A four-fold duplication is an implicit specification.** The
  "unknown environment" check was identical everywhere because it belongs
  to no domain: it bears on `service.environments`, which is the core's.

What the resumption of phase 8 established:
- **The phase 10 guards did their job.** Rebasing the branch
  made three tests fail, and all three were right: a domain delivered without
  its single-domain specification, without its example, and an outdated
  domain count. None of them would have been noticed without them.
- **A witness is worth more than an inspection.** The promise "the pipeline
  knows no domain" is not proven by re-reading the code: it is proven
  with a fake domain the plugin has never seen, and which gets its job.
- **The three defects corrected before the parking each carry their test.**
  Workstation environment variables, deployment order, stdin chaining: they
  can no longer come back silently.

**Next action**: none. The project is delivered, the target complete.

Phase 8 (pipeline) stays on its branch; it can be resumed afterwards. The first domain whose
output **depends on the other sections** of the specification. The point to scope
is not technical: it is reading what the other domains declare without
knowing them, and without the core becoming a scheduler.

What phase 7 established, and which serves phase 8:
- **The promise holds.** Adding a domain cost **one line** of the core
  (`BUILTIN_PLUGINS`). No hook was missing, no type had to be widened —
  unlike phase 3, where `Command.env` had had to be added along the
  way (finding R1).
- **A validator can dictate an architectural decision.** `terraform fmt`
  aligns the `=` of consecutive assignment lines; a template cannot
  align keys whose length it does not know, the projection can. Hence
  `plugins/terraform/hcl.py` and its filters exposed by the
  `<package>.jinja_ext` convention — the first domain to need filters for anything
  other than YAML, and the convention was enough.
- **The real validators still find what the tests do not see.**
  `tflint` reported `var.annotations` declared and never used as soon as the
  `namespace` family was not selected. Fix: the annotations are
  applied to **all** the resources — which their description already
  promised. Hence `test_every_declared_variable_is_used_by_a_template`, which
  exercises **each family in isolation**: the complete case would have masked the defect.
- **CI was not validating what it thought it was validating.** Neither `helm` nor
  `kubeconform` had ever been installed there: the `integration` tests
  were skipping, and a green suite said nothing about the generated projects. The four
  missing validators are now installed there.
- **The facet vocabulary has its first real case.** Terraform and Helm
  both declare `namespaces`: Terraform creates the partition, Helm
  deploys into it. A disagreement means the chart targets a namespace nobody
  creates, and `forge validate` says so without any "if terraform then
  helm" rule existing in the core.

Reminders for phase 8:
- Place the `v1.0.0` tag at the end of phase 10 (`v0.8.0` marks phase 9).
  **Numbering correction**: the phase 6 reminder reserved `v1.0.0`
  for that phase, at a time when it was the last one. The corrected target
  has ten: `v1.0.0` goes back to phase 10, and phases 6 and 7 carry
  `v0.5.0` and `v0.6.0`.
- The `pipeline` domain must know **no** other domain by name.
  What it may read: `manager.domain_names()`, the `DomainInfo`s (including
  `outdir`), the `Command`s returned by `forge_validators`, and the `Projection`s.
  That is already everything needed to generate one job per domain present.
- `Command` already carries `tool`, `argv`, `cwd`, `env` and `install_hint`: a CI
  job derives from that list without the plugin knowing what a chart is.
  The risk is elsewhere — the **installation** of each tool, which `Command` does
  not describe. To be settled in phase 8: infer it from a table specific to the
  pipeline plugin, or widen the contract.

**What phase 7 did NOT do**, and must not be taken for granted:
- the Terraform domain only lays down **Kubernetes** objects (plus `random` and
  `tls`). No cloud provider: credentials would be needed to validate,
  and `forge validate` never reaches any infrastructure;
- `terraform plan` and `apply` are **not** validators: they require a
  cluster. Only `fmt`, `init -backend=false`, `validate` and `tflint` are.

What phase 5 established:
- **Two domains meeting reveal what one alone cannot.** The
  false positive on `hosts` was invisible as long as only one domain existed, and
  DESIGN.md literally proposed the two names that collided.
- The **facet vocabulary** is a shared namespace: adding it to the
  documentation is not enough, the core now compares only the facets
  listed in it. A facet outside the vocabulary is harmless, but has no effect.
- The comparison of projections yields a finding no domain can make
  on its own: "the 'prod' environment is materialised by helm but not by
  ansible". It is a warning, not an error — a service that is only
  containerised is legitimate; what is not is that nobody says so.

Reminders for phase 6:
- Place the `v0.5.0` tag at the end of phase 6 (`v0.4.0` marks phase 5).
  *(This reminder said `v1.0.0`: corrected, see the phase 8 reminders.)*
- Parity divergences 12 to 15 (outdated mentions of `ansible-forge` and
  `helm-forge` in the generated READMEs) must be lifted **in one block**, by
  re-blessing the snapshots in the same commit — it is the right moment,
  since `_legacy/` disappears and parity then stops being useful.
- `tests/specs/two-domains.yml` is the natural candidate for `examples/`. Entry points: `MIGRATION.md` §4 (classification by artefact) and
§7 (state of the Ansible port, including the divergences not to reproduce); `DESIGN.md`
§3 (`helm:` section) and §8 Q6.

What phases 3 and 4 established, and which serves phase 5:
- **The porting pattern**: freeze the parity snapshot first, convert
  next, loop until zero divergence. It held twice.
- **Parity does not degrade when you add**, provided the additions are written
  inert for the frozen cases. That is what made it possible to create nine
  Helm families without losing a single one of the 32 reference files.
- **The real validators find what the tests do not see**, and
  conversely: ansible-lint found 255 violations in a file that
  parity declared perfect; the full render test found a StatefulSet
  deprived of its Service, which no validator could see.

Reminders for phase 5:
- Place the `v0.4.0` tag at the end of phase 5 (`v0.3.0` marks phase 4).
- The two domains already declare comparable facets: Ansible exposes
  `hosts` and `groups`, Helm exposes `hosts` and `namespaces`. The core's
  generic comparison (`validate/consistency.py`) is written but has never had
  two domains to compare on the same specification: that is the heart of
  phase 5.
- `forge update` and `forge diff` have existed since phase 2 and are tested; phase
  5 asks to add to them the test of an update **after a deliberate
  modification of a template** — the temporary template repository pattern
  (`tests/test_cli_coverage.py::_template_repository`) already allows it.

## Arbitration — the eight alert names (2026-09-26)

The English-first pass reached one set of identifiers it could not simply
translate. The eight alert names produced by the `monitoring` domain are French,
and unlike every other rename in that pass this one is **not**
behaviour-preserving: `alertname` is a label Alertmanager matches on, from
configuration that lives outside anything forge generates.

Three options were put to the board. **Option 1 was chosen — rename, and treat it
as breaking.** The record, so it is not reopened without a new reason:

| Option | Outcome |
|---|---|
| 1. Rename, treat as breaking | **Chosen.** English names, migration note in `CHANGELOG.md` and in the generated `monitoring/README.md`. |
| 2. Rename for new projects only, keep old names on `forge update` | Rejected: needs a name-pinning mechanism forge does not have, and leaves two populations of generated projects diverging permanently. |
| 3. Leave them French, document the exception | Rejected: would make these the one permanent French identifier in generated output, against the whole point of the English-first work. |

**What made option 1 free.** The cost of a breaking change is paid by users who
already run the thing being broken, and that population was confirmed empty
before the decision, not assumed: the repository is private (unauthenticated
GitHub API returns 404), `iac-forge` has never been published to PyPI, and the
publication work is still open. The eleven git tags through `v1.1.1` are local
tags with no release and no package behind them, so they do not imply adoption
either. Had forge been published, option 2 would have been the honest answer
despite its cost.

**The trap, recorded because it will recur.** `promtool test rules` is green
across this rename and proves nothing about it. promtool checks a rule file
against its own test file; a rename touches both sides in one pass, so the
validator that normally makes this domain trustworthy is silent precisely where
the risk is. Any future change to a *label value* in generated output — not just
alert names — inherits this blind spot. The same reasoning applied in reverse to
the earlier monitoring fixture rename, where promtool genuinely was the proof,
because the fixture values only had to agree with assertions that moved with them.

### Arbitration — the service-name prefix on alert names

The board also asked for the `alert_prefix()` convention (`boutique` +
`TargetDown` → `BoutiqueTargetDown`) to be reconsidered. Tracked separately
because it is a second breaking change with its own argument, then decided and
landed on its own: **the prefix is dropped.** The names are now bare
`TargetDown`, `HighErrorRate` and so on, and `alert_prefix()` no longer exists.

| Option | Outcome |
|---|---|
| 1. Drop the prefix | **Chosen.** The service was carried twice: once as the `service` label `derive.py` already sets, once baked into the identifier. The label is what Alertmanager matches on. |
| 2. Keep it | Rejected: a cross-service route becomes `alertname=~".*TargetDown"`, which also matches an unrelated alert ending in those characters, and a shared runbook or community dashboard keyed on `TargetDown` stops applying by construction. |
| 3. Opt-in through `monitoring.alert_prefix` | Rejected, but not because it was expensive — one spec field and one branch. **Adding** it later is additive and breaks nobody; shipping it now and removing it later is a second break on the same identifiers. Dropping first keeps the later move free. |

**The shared-receiver cost, which was the original justification.** An operator
reading a notification from one Alertmanager fed by several services sees
`TargetDown` and does not know whose. Real, and paid in the notification rather
than in the routing: one `{{ .Labels.service }}` in the receiver template fixes
it for every alert, including the ones forge did not generate. The prefix did
not actually solve it either — a shared receiver in a Kubernetes cluster already
gets unprefixed `TargetDown` and `KubePodCrashLooping` from the
kube-prometheus-stack and node-exporter mixins, so labels have to be read
regardless; prefixing only made forge's output the one thing in the cluster not
following the convention.

**The cost accepted, and documented.** forge's `TargetDown` now shares a name
with kube-prometheus-stack's, which has a different expression, so a route on
`alertname="TargetDown"` catches both. That is the convention working as
intended — `service` and `env` disambiguate — but the generated
`monitoring/README.md` and `CHANGELOG.md` both say so explicitly rather than
leaving an operator to discover it.

**Same empty-population argument, re-confirmed rather than inherited.** Checked
on 2026-10-06, not carried over: `pypi.org` and `test.pypi.org` both return 404
for `iac-forge`, and the repository is still `PRIVATE`. The failed `Release` run
of 2026-09-26 published nothing. Had it published, option 3 would have become
the strong answer instead of the weakest.

**And the same promtool blind spot**, for the same reason: the rename moved the
`alert:` field and the `alertname` assertion in one pass, so `promtool test
rules` stayed green and proved nothing about it. One thing the alert rename did
not have to deal with: the fingerprint does not report
`grafana/dashboards/<service>.json`, because its `description` is normalised as
prose — and that is where the eight panel cross-references to alert names live.
The golden tree is their only coverage, so they were verified one by one in the
diff instead of being taken on the fingerprint's word.

## Session log

- Session 1 (2026-08-23): phase 0 (bootstrap) then phase 1 (audit + design).
- Session 2 (2026-08-23): phase 2 (complete core, `demo` plugin, golden tests, CI),
  then adversarial review of the core: 25 defects confirmed and corrected, test
  suite taken from 129 to 179 cases.
- Session 3 (2026-08-25): phase 3 (Ansible plugin ported at full parity,
  50 templates converted, 7 roles, real validators passing). 213 tests.
- Session 4 (2026-08-25): phase 4 (Helm plugin ported at 32/32 parity, then nine
  resource families created; 5 defects found by the completion),
  then interface review arbitrated: `forge_check_spec` hook added, `tree.py`
  left to the plugin under a mandatory test. 245 tests.
- Session 5 (2026-08-25): phase 5 (cross-domain checks genuinely
  exercised; facet false positive corrected, shared vocabulary introduced,
  two-domain specification and its nine real validators). 260 tests.
  Then a **target correction**: the brief named five plugins, `CLAUDE.md` had
  reduced them to two. Plan extended, scoping of the domain choice corrected
  (phase 6). 271 tests.
- Session 6 (2026-08-26): phase 7 (Terraform plugin written from scratch — seven
  families, 24 templates, eight real validators passing). One defect found
  by tflint and corrected; the phase 4 CI gap filled. 319 tests.
  Then phase 8 started (pipeline domain) and **parked on the branch
  `phase-8-pipeline`** at the user's request, to consolidate first
  the choice of domains: tests derived from the registry, `examples/` delivered,
  README refocused. 342 tests.
  Then phase 9 (monitoring plugin: six families, eight alerts, each delivered
  with the unit test that proves it fires). Two defects found
  by promtool and by the generic guard. 531 tests.
  Then phase 10 (finishing): critical review, four-fold duplication
  factorised, parity divergences lifted in one block, `_legacy/` and parity
  removed, complete README. 515 tests. Project delivered, `v1.0.0`.
  Then the resumption of phase 8: branch rebased on master, pipeline domain
  finished and tested (two dialects, witness through a fake domain, the three
  defects locked down). 568 tests. **Target complete: the five domains of the
  brief are delivered.**
- Session 7 (2026-09-26): ZED-12, found while preparing publication. forge had
  **never** been usable from an install — the template root was looked up at the
  repository root, which no wheel has — and no test saw it, because every test runs
  from a checkout. `copier.yml` and `partials/` are now shipped inside the package
  as well (`force-include`), and `template_root()` prefers the repository root and
  falls back to the package. Preferring the repository is the whole point: it is the
  only shape copier treats as a versioned template, so a checkout keeps
  `forge update` and its `_commit` line, and its output stays byte-identical —
  goldens and fingerprints untouched. An installed forge loses `update`, which is
  copier's constraint and is written down in DESIGN.md §8 Q2-bis. The two tests that
  would have caught the defect are in `test_cli.py`, one of them installing the
  built wheel into a throwaway virtualenv and comparing the result against a golden
  tree.
