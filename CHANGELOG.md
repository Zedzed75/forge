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

[Unreleased]: https://github.com/Zedzed75/forge/commits/master
