# Changelog

Everything that changes what forge *puts in your repository* is recorded here:
the files it generates, the identifiers inside them, and the command-line
contract. Internal refactors, test-suite work and documentation of the forge
repository itself are not — read `git log` for those.

Read this file before running `forge update` on a project that was generated a
while ago. `forge update` replays the template through copier: it will move
whatever moved here, and an entry marked **Migration** names something you have
to do yourself, outside the generated files, because forge cannot reach it.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Versions here are the
versions of `iac-forge` on PyPI: `1.1.0` is the first one published, so everything
forge had accumulated before it is recorded under that heading rather than spread
over releases that were never cut.

## [Unreleased]

## [1.1.0] - 2026-10-09

First published release. `pip install iac-forge` installs the `forge` command from
here on; everything below was already in the repository and is listed because this
is the release that makes it reachable.

### Changed

- **The monitoring file descriptions recorded in `.copier-answers.yml` are
  English.** The monitoring domain records, for each file it writes at the
  `monitoring/` level, a one-sentence description of what that file is for. Four
  of them were French:

  | File | Before | After |
  | --- | --- | --- |
  | `README.md` | Ce fichier : ce qui est surveille, et comment. | This file: what is watched, and how. |
  | `.gitignore` | Exclut les donnees du collecteur et les rendus locaux. | Excludes the collector data and the local renderings. |
  | `.copier-answers.yml` | Reponses du gabarit, relues par `forge update`. Ne pas editer. | Template answers, read back by `forge update`. Do not edit. |
  | `Makefile` | Raccourcis : `make check`, `make test`, `make check ENV=prod`. | Shortcuts: `make check`, `make test`, `make check ENV=prod`. |

  They appear in exactly one generated file, `monitoring/.copier-answers.yml`,
  and nowhere else: no template reads them, and the generated `README.md`
  composes its own sentences. They are in the answers file only because the whole
  `domain` dict is serialised there.

  No migration. `.copier-answers.yml` is generation plumbing — copier reads it
  back to replay the template, and it reads the keys, not the prose. Nothing
  outside the file matches on these sentences.

- **Generated alert names are English.** The eight alerts produced by the
  `monitoring` domain were named in French. Only the words changed here; the
  service-name prefix in front of them is removed by the next entry, and the two
  compose — a service called `boutique` had `BoutiqueCibleInjoignable` and now
  has `TargetDown`:

  | Before | After |
  | --- | --- |
  | `CibleInjoignable` | `TargetDown` |
  | `TauxErreurEleve` | `HighErrorRate` |
  | `LatenceElevee` | `HighLatency` |
  | `MemoireProcheDeLaLimite` | `MemoryNearLimit` |
  | `CpuEleve` | `HighCpuUsage` |
  | `RedemarragesEnBoucle` | `ContainerRestartLoop` |
  | `SondeExterneEnEchec` | `ExternalProbeFailed` |
  | `CertificatBientotExpire` | `CertificateExpiringSoon` |

  `forge update --only monitoring` rewrites all of it: the `alert:` field in
  `rules/<env>/<family>.yml`, the `alertname` assertion in the matching
  `tests/<env>/<family>.yml`, the panel descriptions in the Grafana dashboard,
  and `.copier-answers.yml`. Afterwards `promtool test rules` is green — and you
  should not read that as reassurance. promtool checks each rule against its own
  test file, and both sides moved in the same pass, so it would stay green however
  badly this broke your alerting.

  **Migration.** `alertname` is a label, and Alertmanager matches on it from
  configuration forge neither owns nor can see. Nothing below reports an error;
  each one simply stops working:

  - **routes** that select on `alertname` no longer match, so the alerts they
    directed fall through to your default receiver;
  - **inhibition rules** no longer inhibit, so an alert a more serious one used to
    suppress now pages alongside it;
  - **silences** are matcher objects stored in Alertmanager, keyed on the label
    value. A silence on an old name still shows as active while silencing nothing.

  Before merging a `forge update --only monitoring`: grep your Alertmanager
  configuration for the old names in the table above, update every matcher, and
  re-create any silence that was active. The generated
  `monitoring/README.md` carries the same warning next to the names your project
  produces now.

- **Generated alert names no longer carry the service name.** The eight alert
  names were prefixed with the service name in CamelCase; they are not any more.
  A service called `boutique` had `BoutiqueTargetDown` and now has `TargetDown`:

  | Before | After |
  | --- | --- |
  | `<Service>TargetDown` | `TargetDown` |
  | `<Service>HighErrorRate` | `HighErrorRate` |
  | `<Service>HighLatency` | `HighLatency` |
  | `<Service>MemoryNearLimit` | `MemoryNearLimit` |
  | `<Service>HighCpuUsage` | `HighCpuUsage` |
  | `<Service>ContainerRestartLoop` | `ContainerRestartLoop` |
  | `<Service>ExternalProbeFailed` | `ExternalProbeFailed` |
  | `<Service>CertificateExpiringSoon` | `CertificateExpiringSoon` |

  The service is not lost: every generated rule already carries it as the
  `service` label, next to `env` and `severity`, and that label is the instrument
  Alertmanager is designed to match on. Carrying it in the identifier as well
  made a cross-service route a regex (`alertname=~".*TargetDown"`, which also
  matches an unrelated alert ending in those characters) and stopped a shared
  runbook or a community Grafana dashboard keyed on `TargetDown` from applying.
  `TargetDown` and the other names are the Prometheus convention precisely
  because the series' own labels disambiguate.

  Same files as the entry above, rewritten by the same
  `forge update --only monitoring`, and the same warning about `promtool test
  rules`: green across this change, and green however badly it broke your
  alerting.

  **Migration.** Identical mechanism to the entry above — `alertname` is a label
  matched from Alertmanager configuration forge neither owns nor can see — so the
  same three things break silently: **routes** selecting on `alertname` stop
  matching and fall through to your default receiver, **inhibition rules** stop
  inhibiting, and **silences** keep showing as active in the UI while silencing
  nothing. Grep your Alertmanager configuration for the prefixed names, update
  every matcher, and re-create any silence that was active.

  One new thing to check, which did not apply while the names were prefixed: the
  generic names **collide by design** with the ones kube-prometheus-stack and the
  node-exporter mixins ship. A route on `alertname="TargetDown"` now catches this
  service's alert and theirs. That is the convention working as intended, but if
  you want only this service, add `service="<your-service>"` to the matcher.

- **Generated CI job identifiers are English.** Every job key and job name in
  the generated `.github/workflows/ci.yml`, and every job key *and* stage name
  in the generated `.gitlab-ci.yml`, was renamed:

  | Before | After |
  | --- | --- |
  | `valider-<domain>` / `Valider <Domain>` | `validate-<domain>` / `Validate <Domain>` |
  | `construire` / `Construire l'image` | `build` / `Build the image` |
  | `deployer-<env>` / `Déployer <env>` | `deploy-<env>` / `Deploy <env>` |
  | GitLab stages `valider`, `construire`, `deployer` | `validate`, `build`, `deploy` |

  Inside the generated file this is self-consistent — `needs:` is rewritten in
  the same pass — so the pipeline itself keeps working after
  `forge update --only pipeline`.

  **Migration.** A job name is also the name of the *required status check* that
  a GitHub branch-protection rule matches on, and forge does not own that rule.
  A rule that requires `Valider Helm` stops matching once the job is called
  `Validate Helm`: the check it waits for is never reported, and the next pull
  request on that repository cannot be merged until someone with admin rights
  edits the rule. Before merging a `forge update --only pipeline`, open
  *Settings → Branches → your rule → Require status checks to pass* and rename
  each entry to its new spelling. The same applies to anything else that names a
  job from outside the file: a GitLab `needs:` in a downstream pipeline, a
  `workflow_run` trigger in another repository, a dashboard, or a chat
  notification filter.

- **Generated Terraform and Prometheus identifiers are English.** In the
  Terraform secret module, the comprehension
  `{ for cle, motdepasse in random_password.generated : cle => motdepasse.result }`
  became `{ for key, password in random_password.generated : key => password.result }`.
  In the generated `promtool` test fixtures, the placeholder values
  `instance-de-test:9090`, `pod-de-test`, `conteneur-de-test` and
  `https://sonde-de-test.invalid` became `test-instance:9090`, `test-pod`,
  `test-container` and `https://test-probe.invalid`.

  No migration. The HCL names are local to one expression, and the promtool
  values only have to agree with the assertions in the same generated file,
  which move with them. Both are listed here because they change bytes that
  `forge update` will rewrite in your working tree.

- **Generated projects are written in English.** The header comments, task and
  resource names, variable documentation and GitHub Actions step labels produced
  by the `ansible`, `helm`, `terraform`, `monitoring` and `pipeline` domains are
  now English, as are the repository-root `README.md`, `forge.yml` header and
  `.gitattributes` that forge scaffolds around them.

  No migration, but expect a large diff: this touches the prose in nearly every
  generated file. If you have edited a generated file by hand, `forge update`
  will report conflicts there — run `forge diff` first to see how much moved.

- **The `demo` domain is written in English too.** Its templates, catalogue
  entries, validator label and interview prompts are now English, and the
  `demo-full` and `demo-minimal` golden trees moved with them.

  **No migration, and this one cannot reach you.** `demo` is not a shipped
  domain: it is the fixture the core's own suite runs the plugin contract
  against, it is absent from `BUILTIN_PLUGINS`, and it loads only when
  `FORGE_PLUGINS` names it explicitly. No `forge generate` a user can run
  produces a `demo/` directory, so no `forge update` rewrites one. It is
  recorded here because it moved a golden — the trigger this changelog is
  written against — not because it changes anything forge puts in your
  repository.

- **`forge update` now explains itself instead of failing obscurely when the
  template is not git-tracked.** copier merges by comparing two git references, so
  `forge update` needs the template to be a git repository. A checkout is one and is
  unaffected. An installed forge is not — it renders from `site-packages/forge/`,
  which carries no history — and the command now says so, pointing at
  `forge generate --force` (regenerate without merging) or at
  `FORGE_TEMPLATE_SRC=<a git clone of the forge repository>` (keep the merge).
  Previously it surfaced copier's own "Updating is only supported in git-tracked
  templates", which never said *which* of the two repositories it meant.

  **Migration.** None if you use forge from a checkout. If you rely on
  `forge update` from a `pip install`, point `FORGE_TEMPLATE_SRC` at a clone of this
  repository, or switch to `forge generate --force` and reapply your local edits by
  hand.

- **Projects generated by an installed forge record no `_commit`** in their
  `.copier-answers.yml`, and write `template_subdir` as `plugins/<domain>/template`
  rather than `src/forge/plugins/<domain>/template`. Both are copier's doing: it
  only records a template commit for a git-tracked template, and the path is
  relative to whichever template root produced the project. Projects generated from
  a checkout are unchanged, and nothing else in the generated tree differs between
  the two.

### Fixed

- **`forge generate` works from an installed forge.** Installing the wheel and
  running `forge generate` used to fail with "template root not found" and leave the
  output directory empty: the templates were looked for at the repository root,
  which no installation has. forge had only ever been usable from a clone of its own
  repository, and nothing in its test suite noticed, because every test runs from a
  clone. `copier.yml` and `partials/` are now shipped inside the package as well, so
  an install renders the same project a checkout does — verified by installing the
  built wheel into a fresh virtualenv and comparing the result against the
  reference tree.

  Nothing changes for anyone running forge from a checkout: same output, byte for
  byte.

[Unreleased]: https://github.com/Zedzed75/forge/compare/v1.1.0...master
[1.1.0]: https://github.com/Zedzed75/forge/releases/tag/v1.1.0
