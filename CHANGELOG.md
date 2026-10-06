# Changelog

Everything that changes what forge *puts in your repository* is recorded here:
the files it generates, the identifiers inside them, and the command-line
contract. Internal refactors, test-suite work and documentation of the forge
repository itself are not — read `git log` for those.

Read this file before running `forge update` on a project that was generated a
while ago. `forge update` replays the template through copier: it will move
whatever moved here, and an entry marked **Migration** names something you have
to do yourself, outside the generated files, because forge cannot reach it.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
forge is not versioned or tagged yet, so every entry currently lives under
`Unreleased`; the first tagged release will close that section and start the
next one.

## [Unreleased]

### Changed

- **Generated alert names are English.** The eight alerts produced by the
  `monitoring` domain were named in French. Each generated name is the service
  name followed by one of these suffixes, so a service called `boutique` had
  `BoutiqueCibleInjoignable` and now has `BoutiqueTargetDown`:

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

- **Generated CI job identifiers are English.** Every job key and job name in
  the generated `.github/workflows/ci.yml`, and every stage name in the
  generated `.gitlab-ci.yml`, was renamed:

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

- **Generated projects are written in English.** The header comments, task and
  resource names, variable documentation and GitHub Actions step labels produced
  by the `ansible`, `helm`, `terraform`, `monitoring` and `pipeline` domains are
  now English, as are the repository-root `README.md`, `forge.yml` header and
  `.gitattributes` that forge scaffolds around them.

  No migration, but expect a large diff: this touches the prose in nearly every
  generated file. If you have edited a generated file by hand, `forge update`
  will report conflicts there — run `forge diff` first to see how much moved.

[Unreleased]: https://github.com/Zedzed75/forge/commits/master
