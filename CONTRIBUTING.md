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
`.github/actions/forge-ci-setup/action.yml`, which is where the pinned installs
live, and `.github/workflows/ci.yml` for the jobs that call
it. Note that `ansible-core` does not support Windows as
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

### Which CI checks gate a merge

Four check-runs per event, and only three of them are a gate:

| Check | Runner | Gates a merge? |
| --- | --- | --- |
| `tests (3.11)`, `tests (3.12)`, `tests (3.13)` | `ubuntu-24.04` | **yes** |
| `canary (3.13, ubuntu-26.04)` | `ubuntu-26.04` | no |

The canary runs the same suite, from the same composite action, with the same
`FORGE_REQUIRE_TOOLS=1`, on the image `ubuntu-latest` is migrating to.

What `continue-on-error: true` does and does not do, measured rather than read
off the documentation — a deliberately failing canary was pushed on a throwaway
branch to watch it:

| | when the canary fails |
| --- | --- |
| workflow **run** conclusion | `success` |
| the canary **job** conclusion | `failure` |
| its **check-run** conclusion | `failure` |

So the flag makes the *run* green, not the *check*. The canary stays visibly red
exactly where you will look: `gh pr checks` reports a failure, and so does the
PR page. **That is not a gate, and it is not yours to fix** unless your change
caused it — it is reporting something about the Ubuntu 26 image, which is what
`D10` asks it to do before the pin moves onto that image. Read it, say in the PR
that you read it, and merge on the three `tests` legs.

This is the one place where "all checks green" and the merge standard come
apart, so do not automate over it. A poll that waits for every check-run to turn
green will wait forever on a red canary; `D4`'s count is a count of *gating*
checks.

What a red canary is worth reporting on, though, is `ZED-72`: a validator that
stops installing on 26.04 is exactly the finding the job exists to produce, and
it needs to reach the issue that owns the upgrade rather than sit in a log.

### Running the CI matrix locally, in Docker

CI is the authority because it is the only Linux host where all five domains'
validators run natively. When CI is unavailable, that authority can be produced
locally instead — in a Linux container, not on the host:

```bash
./scripts/docker-matrix.sh                    # HEAD of the current worktree
./scripts/docker-matrix.sh --ref my-branch    # a named local branch
./scripts/docker-matrix.sh --python 3.12      # one cell, for a quick look
./scripts/docker-matrix.sh --verify-pins-only # drift check only, no containers
```

This runs the same suite on the same three interpreters with the same pinned
validators and the same `FORGE_REQUIRE_TOOLS=1`, so a missing validator fails
the run instead of skipping. It needs a Docker daemon with a **Linux** engine
and refuses to run against a Windows one. The sources travel as a git bundle, so
the worktree must be clean — the bundle carries commits only, and a result that
does not correspond to a commit cannot be recorded against a pull request.

The container declares the toolchain a second time
(`scripts/docker/Dockerfile.ci-matrix` and `scripts/docker/run-matrix.sh`), and
a second declaration rots. Every run therefore starts by extracting each pinned
version from those two files and requiring it to appear verbatim in CI's own
declaration; a bump on either side stops the run. When you bump a validator,
bump it in both places in the same commit.

CI's declaration of the toolchain is `.github/actions/forge-ci-setup/action.yml`
rather than the workflow: the install steps live in a composite action so that
the gating job and the `ubuntu-26.04` canary below share one toolchain instead
of two copies that drift apart. The workflow is still where the interpreter
matrix is read from.

What this is **not**: a `-m "not integration"` run, a single interpreter, a run
on the Windows host, or a run with validators missing. Two bugs in this
repository's history (`223cae4`, `f050a05`) were visible only on Linux with the
real validators present, which is exactly why the weaker forms do not
substitute. See `D6` in `DECISIONS.md` for when a matrix run of this kind may
stand in for green checks, and for the `.github/workflows/**` exception — a
container cannot exercise `uses:` pins, caching, OIDC or trigger behaviour, so a
change to the workflow itself is not validated this way. `D7` narrows that
exception to the behaviours it names; the next two sections are its two tests.

### Is a workflow diff prose? (`D7`, clause C1)

A pull request that changes a file under `.github/workflows/**` is parked by
`D6`. `D7` lets it through — and *only* through — when every changed line in
those files is prose and nothing else. **Clause C1 in `DECISIONS.md` is where the
list of line kinds that count as prose lives**; do not read it off this page,
because a list kept in two places diverges (`D13`). It is a question with an exit
code, not a judgement call, and this script is the clause:

```bash
./scripts/workflow-diff-is-prose.sh origin/master my-branch
```

Exit 0 means clause C1 passes; exit 1 names the lines that fail it; exit 2 means
the witness could not run (bad revision, no Python) and has decided nothing.

The test works by normalising each file at each revision — erasing exactly what
C1 calls prose and copying everything else — and comparing the two skeletons
(`scripts/workflow_prose_skeleton.py`). A key the normaliser has never heard of
is copied, so a change to it fails: the test is fail-closed by construction
rather than by keeping a list of forbidden keys in step with the workflow
syntax. C1 names two exclusions that a reader guesses wrong, and
`tests/test_workflow_prose_policy.py` pins both — read them in `D7`, with the
reason each one is there.

### What does the change break? (`D7`, clause C2)

The matrix reimplements `ci.yml`, so it witnesses the workflow file not at all.
`actionlint` reads it, and its shellcheck pass catches the one way a translation
really breaks a workflow — quoting damage inside a string it rewrote:

```bash
./scripts/actionlint-differential.sh origin/master my-branch
```

Exit 0 means the head introduces no finding the base does not already carry.
The gate is **differential, never absolute**: `master` carries one finding
today, and an absolute "actionlint clean" gate would refuse every workflow PR
until someone unrelated fixed it. Findings are matched on file, rule and
message, never on line number, because a prose change moves every line below it.

It runs in the matrix image itself (`scripts/docker/Dockerfile.actionlint` adds
one thing to it: a pinned `shellcheck`, which actionlint only uses when it finds
it on PATH), so the actionlint doing the reading is the one `ci.yml` pins. Same
requirement as the matrix: a Docker daemon with a Linux engine.

Both scripts speak about their own clause only. A workflow PR merges under `D7`
when C1, C2, a full matrix run (C3) and a post-merge `verify_pins` (C4) all
pass — see `D7` in `DECISIONS.md`.

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

`tests/test_french_guard.py` enforces that for `src/forge/**/*.py`, for the
plugin templates, for `partials/` and for `tests/**/*.py`, and those are
measured clean — so if it goes red, the French is yours. Translate the line.

`tests/french_baseline.txt` holds the two escape hatches, and they are not
interchangeable:

- `[allowed]` is for French that has to stay French to work — a fixture
  asserting that a non-ASCII name is rejected, say. One justification per
  entry, permanent, and reviewed as such.
- `[baseline]` is a per-file line count for French awaiting translation. It
  ships **empty** and **only ever shrinks**: translating lines fails too, with
  the number to lower the entry to, so the remaining work stays countable.
  Adding an entry means landing new French and needs an argument on the PR — it
  is not the way to turn a red build green. The section exists for a widening
  of the scope, which cannot translate thousands of lines in the same commit
  that starts scanning them.

The guard reads three signals — accented characters, two French function words
on one line, and one French content word in a prose-shaped value such as a
`description` or an `owner`. It is deliberately conservative, so it catches new
French rather than proving none remains: `tests/french_guard.py` lists all three
signals *and* what none of them can see, which is the part to read before
concluding from an empty `[baseline]` that a tree is clean. ZED-69 is the
cautionary tale — the first two signals reported zero while eleven test modules
held 32 French values, because `Equipe Plateforme` has no accent and no function
word. Two review tools live in `tests/review/`: given two
revisions, `skeleton.py` proves no condition or exception type changed, and
`keys.py` proves no spec, section or catalog key was renamed. Run them on a PR
that rewrites prose across a domain, where a golden diff proves nothing.

## Reporting bugs and requesting features

Use the issue templates under `.github/ISSUE_TEMPLATE/`. For a bug, the single
most useful thing you can include is the `forge.yml` spec that reproduces it,
reduced to the smallest version that still fails.

Security issues do **not** go in a public issue — see [SECURITY.md](SECURITY.md).

## Licence

By contributing, you agree that your contributions are licensed under the MIT
Licence, as covered by the [LICENSE](LICENSE) file.
