# Contributing to forge

Thanks for your interest in forge. This document covers how to get a working
development environment, how to run the test suite, and the rules a change has
to follow to be merged.

## Development environment

forge targets Python 3.11, 3.12 and 3.13. The project uses
[uv](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
git clone https://github.com/Zedzed75/forge.git
cd forge
uv sync --extra dev
```

`uv sync` creates `.venv/` in the repository root and installs forge in editable
mode. Activate it (`source .venv/bin/activate`, or `.venv\Scripts\activate` on
Windows), or prefix every command with `uv run`.

Use `uv sync` and not `uv pip install -e ".[dev]"`: every constraint in
`pyproject.toml` is a floor, and installing from the floors resolves whatever
PyPI serves today. `uv sync` installs `uv.lock` instead — the exact versions CI
uses, `copier` and `jinja2` among them. Those two **are** the renderer, so a
different version of them can change generated output and make the golden trees
or the structural fingerprints fail for you and pass in CI, or the reverse. The
reasoning is written up in `DESIGN.md` §8 Q10.

CI runs `uv sync --locked`, which refuses to resolve and fails if `uv.lock` has
fallen behind `pyproject.toml`. So if you change a dependency, run `uv lock` and
commit the result with it.

### Optional: domain validators

forge's promise is that a generated project passes the *real* validators of its
domain, not an internal check. The tests that exercise those validators are
marked `integration` and are **skipped silently when the tool is missing** — so
a green suite on a bare machine does not prove much. The full set is:

| Domain | Tools |
| --- | --- |
| Ansible | `ansible-core`, `ansible-lint` |
| Helm | `helm`, `kubeconform` |
| Terraform | `terraform`, `tflint` |
| Monitoring | `promtool` (from Prometheus) |
| Pipeline | `actionlint`, `yamllint` |

Installing all of them locally is optional. CI installs every one of them on
Linux and is the authority on whether generated output is valid — see
`.github/workflows/ci.yml`. Note that `ansible-core` does not support Windows as
a control node; on Windows the Ansible validators run through WSL.

## Running the tests

```bash
uv run pytest            # the whole suite
uv run pytest -m "not integration"   # skip anything needing an external tool
uv run pytest tests/test_cli.py      # one file
```

Determinism is a hard guarantee: the same spec must always produce the same
output, and golden tests under `tests/golden/` enforce it. If your change
legitimately alters generated output, update the goldens in the same commit and
explain in the PR *why* the output changed.

## Making a change

- **Never commit to `master`.** Branch off it, push the branch, open a pull
  request. `master` is only updated through merged PRs.
- Keep commits logical: one concern per commit, no unrelated reformatting mixed
  into a functional change.
- Write the commit subject as a statement of what was wrong or what the change
  achieves, in the style of the existing history (`git log --oneline`).
- CI must be green before a PR is merged. It runs the suite on all three
  supported Python versions with every validator installed.

### Changes to generated output need a changelog entry

**If your PR moves a golden file, it must also add an entry to
[CHANGELOG.md](CHANGELOG.md)** under `## [Unreleased]`, in the same commit. A
moved golden is the definition of a user-visible change: it is exactly what
`forge update` will rewrite in someone's repository.

Write the entry for the person running that update, not for a reviewer reading
the diff. Say what the old spelling was and what the new one is, and — this is
the part that is easy to skip — say whether anything *outside* the generated
files has to change too. A renamed CI job is also the name of a required status
check in a branch-protection rule that forge cannot reach; a renamed alert is
also a matcher in someone's Alertmanager routes and silences. When such a step
exists, label it **Migration** so it cannot be read as trivia.

If the change is genuinely inert — prose, a comment, a local loop variable — say
so and say why. "No migration" is a useful entry; a missing entry is not.

`CHANGELOG.md` is user-facing, so it is English, like `README.md`,
`CONTRIBUTING.md` and `SECURITY.md`. It records changes to what forge *produces*
and to the CLI contract; a refactor, a new test or a documentation fix inside
this repository does not belong there.

## Architecture rules

These are load-bearing. A change that breaks one of them will be sent back:

- **Core is domain-agnostic.** Everything under `src/forge/core/` must work
  without knowing that Ansible or Helm exist. Domain knowledge lives only in
  `src/forge/plugins/<domain>/`.
- **Adding a domain must not require touching core.** Plugins register through
  pluggy hooks; that contract is what makes a new domain a drop-in.
- **Rendering goes through copier** (library mode). Never hand-roll template
  rendering.
- **Anything the renderer reads must reach the wheel.** The template root is the
  repository root from a checkout and `site-packages/forge/` from an install, so a
  file the renderer needs has to be either under `src/forge/` or listed in the
  `force-include` table of `pyproject.toml`. Miss that and an installed forge
  cannot generate at all, while every test keeps passing — they all run from a
  checkout, where the path resolves anyway. That is exactly how the bug
  DESIGN.md §8 Q2-bis describes got in.
- **Templates use copier's custom delimiters** `[[ ]]`, `[% %]` and `[# #]`.
  This is deliberate: Helm and Ansible both use `{{ }}` in *their* output, and
  those braces must pass through untouched. Never write `{{ }}` meaning "a
  generator variable".
- **Every generated file is commented**: a header saying what the file is for,
  explicit names on tasks and resources, and a comment on every user-facing
  variable describing its purpose and allowed values. A generated project is
  meant to be read, not just run.
- Use FQCN for Ansible modules. Follow Helm best practices (helpers,
  `app.kubernetes.io` labels, no hardcoded values). Never invent a module or a
  resource kind that does not exist.

Write everything in English: comments, docstrings, prose, documentation,
identifiers, keys and file names, both here and in the projects forge generates.
The repository was originally written with French comments and is being
translated, so a file that still reads French is a leftover, not the convention —
follow `CLAUDE.md`, not the file next to yours. `DESIGN.md` records the
architectural decisions and the reasoning behind them; read it before proposing
a structural change.

## Reporting bugs and requesting features

Use the issue templates under `.github/ISSUE_TEMPLATE/`. For a bug, the single
most useful thing you can include is the `forge.yml` spec that reproduces it,
reduced to the smallest version that still fails.

Security issues do **not** go in a public issue — see [SECURITY.md](SECURITY.md).

## Licence

By contributing, you agree that your contributions are licensed under the MIT
Licence, as covered by the [LICENSE](LICENSE) file.
