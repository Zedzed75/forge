# DECISIONS.md — standing decisions

Standing policy decisions, numbered `D1`, `D2`, … Each one is in force until a
later decision recorded here replaces it. They are **policy**: what engineering
may do, what the board decides, what a given name or language is. The technical
arbitrations of the architecture (`Q1` … `Q9` — delimiters, `copier.yml` layout,
inter-domain checks) are a different thing and live in `DESIGN.md` §8.

Where a decision is cited in an issue thread, the issue is the primary record and
is linked below; this file is the durable copy, because issues close.

A decision is **not** a grant for anything it does not name. D4 in particular
removes a merge card, not an evidence standard: a fingerprint that moves beyond
what a PR predicted is still a stop-and-report, never a re-bless.

---

## D1 — publish as `iac-forge`

- **Date**: 2026-09-25
- **Decided by**: the board, approving the public-release plan on issue ZED-2
  (07:13 UTC). Recorded on ZED-9.

The distribution is published to PyPI under the name **`iac-forge`**. The CLI command and
the import package both stay **`forge`**, and neither is to be aligned with the
distribution name.

`forge` is taken on PyPI (`GET https://pypi.org/pypi/forge/json` → `200`), so
`pip install forge` was never available to this project. `iac-forge` and
`forge-iac` were both free and the board chose `iac-forge`. Only one of the three
names changes: a user types `pip install iac-forge` once, and `forge` forever
after. A change that renames the import package or the console script is outside
this decision and will be sent back.

---

## D2 — translate everything, including internals

- **Date**: 2026-09-25
- **Decided by**: the board, same approval as D1. Recorded on ZED-10.

The English-first work covers **everything, internals included** — plugin
templates, golden fixtures, source comments and docstrings, CLI surface, file and
directory names — not only the user-visible surface.

Recon established that the spec API is already English (`forge_version`,
`service`, `environments`, `chart_version`); only comments and prose *values* were
French, so no existing user `forge.yml` breaks. That removed the compatibility
risk and made the complete translation cheaper to justify than a hedged, partial
one. The scope is large (114 templates, 289 golden fixtures, ~106 Python files in
`src/`), which is why the fail-closed validators and the structural-fingerprint
harness landed first: they are what makes a multi-megabyte, comment-only diff
reviewable at all.

---

## D3 — English throughout, reversing the French-comments rule

- **Date**: 2026-09-25
- **Decided by**: the board, same approval as D1. Recorded on ZED-10, landed as
  its own PR before any translation work.

The `CLAUDE.md` hard rule *"comments/docs in French; identifiers, keys and file
names in English"* is **reversed to English throughout** — comments, docstrings,
prose, documentation, identifiers, keys and file names, in this repository and in
everything it generates.

Every file in the repository was written under the original rule, so reversing it
governs all the translation work that follows; it was put to the board explicitly
rather than left to land implicitly inside a translation PR. It landed first, on
its own small PR, so that every later translation PR has one unambiguous rule to
cite. Consequence worth stating plainly: a file still carrying French is awaiting
translation, never a pattern to copy — including this file, which is in English
for that reason.

---

## D4 — merge on self-review, with three carve-outs

- **Date**: 2026-10-08
- **Decided by**: the CEO. Stated on ZED-47 as the authorization that unfroze the
  merge queue, then **ratified by the CEO as written** on ZED-52, with the
  carve-out 1 clarification below.

A PR that is (a) CI-green on all six checks with `FORGE_REQUIRE_TOOLS=1`,
(b) `MERGEABLE` / `CLEAN` against `master`, and (c) inside a scope the board
already approved, is **merged by engineering on self-review**. No per-PR
confirmation card.

### The three carve-outs (verbatim, from ZED-47)

Exactly three things still need a card, and nothing else does:

1. Changes to publish credentials, permissions, or secrets — not pinning, not
   workflow hygiene: the **authority** the workflow runs with.
2. Generated-output semantics not covered by an approved decision (a rename users
   must migrate for, a changed default, a dropped field).
3. Making the repository public. That one is the board's, and it stays the
   board's.

### Clarifications carried by the ratification (ZED-52)

- **Carve-out 1 is about authority, not shape.** It covers *who may publish, with
  which credentials and permissions* — not the layout of the release path. Adding
  an `id-token` permission, moving a secret, or widening who can trigger a publish
  is carve-out 1 and needs a card. Restructuring the release path within the
  authority it already has — for instance dropping the TestPyPI rehearsal on
  ZED-48 — is inside engineering's authority and needs none.
- **Carve-out 3 is absolute.** Making the repository public must not be inferred
  from any scope approval, including the public-release plan approved on ZED-2.

### Reasoning

The alternative had been measured and it was worse: twelve days with zero merges,
eight PRs open and every one of them 6/6 green, two recovery stalls on ZED-24, and
a `human_only` card on ZED-19 that held a translation the board had *already*
approved under D2 and D3. Self-review was raised as a worry on ZED-30 precisely
because it is what happens by default; it is now the arrangement deliberately,
because a security reviewer this company does not have cannot be the gate on a
queue that has to move. The evidence standard is untouched — see the note at the
top of this file.

---

## D5 — no issue is parked bare

- **Date**: 2026-10-08
- **Decided by**: the CEO, on issue ZED-65. Recorded by engineering on the same
  issue.

An issue may not be left in a waiting state that names nothing capable of ending
it. Concretely:

- **`blocked`** carries either a first-class blocker edge (`blockedByIssueIds`) or
  an `unblockDescriptor` with an owner and an exact action.
- **`in_review`** carries a named reviewer, a pending interaction, or a real
  `monitorNextCheckAt`.
- **"Waiting its turn"** is **`todo`** or **`backlog`** with a priority — never
  `blocked`. An unstarted issue is not blocked, and calling it blocked hides the
  depth of the queue.

### Who sets the disposition

The **owner of an issue sets that issue's disposition.** This is not a formality:
an agent can only write to an issue its current run is attributed to, so a third
party who notices a bare park usually *cannot* fix it. Both a status `PATCH` and a
`blockedByIssueIds` edge aimed at someone else's issue are refused with
`cross_issue_influence_run_context_required`, and on a heartbeat run with no task
binding the blocker edge is refused even after checking the issue out.

So the obligation lands on the owner, and a third party who spots a bare park
**couriers** it — files an issue assigned to the owner naming the issue and the
disposition to set. Taking the issue over instead is the wrong repair: it hides
the work from whoever is actually mid-change on it.

### Reasoning

D4 fixed the *authorization* cause of the frozen queue. This fixes the
*bookkeeping* cause, which is the one that survived it. ZED-47's queue sat for
twelve days; ZED-9 sat for twelve more on a card no agent could answer. In every
case the work was not truly stuck — it moved as soon as an agent happened to look.
That is the defect: the board state did not say to look. A `blocked` issue with no
edge and no descriptor emits no `issue_blockers_resolved` wake, and an `in_review`
issue with no reviewer, interaction or monitor emits nothing at all, so the only
remaining scheduler is luck.

The three issues that prompted this (ZED-31, ZED-23, ZED-56) were all mislabelled
in the same direction — `blocked`/`in_review` for work that was merely unstarted or
simply needed a rebase. That direction is not an accident: parking an issue reads
as caution, so the cautious-looking status is the one picked under doubt. Hence the
rule rather than the case-by-case judgement.

---

## D6 — while Actions is unavailable, the matrix may be produced in Docker

- **Date**: 2026-10-08
- **Decided by**: the CEO, on issue ZED-74. Recorded by engineering on the same
  issue.

GitHub Actions assigns no runner for this repository (ZED-66: jobs fail in three
seconds with zero steps, and the check-run annotation names account billing).
While that lasts, a pull request **may merge on evidence from a local Docker run
of the CI matrix** instead of on the six green checks:

- a **Linux** container (the Docker engine must report `OSType: linux`),
- **all three** interpreters — 3.11, 3.12, 3.13,
- the **whole** suite, with **`FORGE_REQUIRE_TOOLS=1`**,
- the five domains' **validator binaries present**, at the versions
  `.github/workflows/ci.yml` pins,
- and the result **recorded on the pull request's issue**.

`./scripts/docker-matrix.sh` is that run; `CONTRIBUTING.md` documents it. Nothing
weaker qualifies. A single interpreter, a `-m "not integration"` run, or a run
with a validator missing is not D6 evidence and must not be reported as such.

### The exception: `.github/workflows/**`

A pull request that changes a file under `.github/workflows/**` **may not use
this path** and waits for billing. When the workflow is the thing under test,
only a real Actions run exercises it: a container cannot validate `uses:` SHA
pins, Actions caching, OIDC, or trigger behaviour. The four PRs parked under this
rule on the day of the decision were #61, #59, #50 and #49 — including the
Actions-burn fix itself, which cannot prove itself without the thing it modifies.

### This is a change of host, not of standard

Two alternatives were rejected, both of them cheaper:

- **A local Windows green.** This repository's own history forbids it. Commit
  `223cae4` ("Two defaults that only a Linux machine could show") and `f050a05`
  ("helm was validated against the wrong Kubernetes version") are bugs that only
  the Linux matrix caught; `ansible-core` does not even support Windows as a
  control node. Accepting a Windows-local green would have shipped both.
- **Waiving evidence for "obviously safe" changes.** Same objection, and it has
  no edge: every change looks obviously safe to whoever wrote it.

A Linux container catches exactly the class those two commits belong to, which is
why relocating the evidence is sound where weakening it is not. The claim was
checked rather than assumed: the last green Actions run on `master` (`e2a81e5`,
2026-10-08 15:17Z) reported `681 passed, 2 skipped` on each interpreter, with one
skip reason and twelve `integration` tests; the container reproduced that result
exactly, test for test, with the same skip reason and the same twelve. Had it not,
the instruction on ZED-74 was to say so and stop rather than merge on weaker
evidence.

The container declares the toolchain a second time, so every run first requires
each pinned version to appear verbatim in `.github/workflows/ci.yml` and stops on
drift. Evidence from a container pinned to other versions than CI would be a
different environment wearing CI's name.

### Expiry

D6 is **in force until Actions runs again**. It is a workaround with an end
condition, not a new standard: when ZED-66 resolves, the six green checks are the
evidence again and this decision is spent. D4's note at the top of this file is
untouched — the evidence standard was never what moved.

---

## D7 — a workflow change is inside D6 only if a script says it is prose

- **Date**: 2026-10-09
- **Decided by**: the CEO, on issue ZED-84. Recorded by engineering on ZED-85.

D6 parks any pull request that touches `.github/workflows/**` until Actions runs
again. That exception is **behavioural, not file-path**. D6 says so in its own
words — *"a container cannot validate `uses:` SHA pins, Actions caching, OIDC,
or trigger behaviour"* — which is a list of behaviours, written as the reason. A
diff that reaches none of them was never what the exception was protecting
against.

So a pull request touching `.github/workflows/**` may use the D6 path, but only
if **all four** clauses below hold. Any one of them failing and it waits for
billing. There is no judgement call anywhere in here: each clause is a command
with an exit code.

**C1 — the diff is prose, and a script says so.** Every changed line in every
`.github/workflows/**` file is exactly one of: a YAML comment, a **step-level**
`name:` value, or literal text inside an already-quoted string in a `run:`
block. No changed line adds, removes or alters `uses:`, `on:`, `permissions:`,
`env:`, `with:`, `if:`, `needs:`, `runs-on:`, `concurrency:`, `strategy`/matrix,
`defaults`, `secrets`, `outputs`, `timeout-minutes`, `continue-on-error`, a
`jobs.<id>` key, a **job-level** `name:`, a redirection, or a pinned version.

```bash
./scripts/workflow-diff-is-prose.sh origin/master my-branch
```

Two exclusions are deliberate. A **job-level** `name:` is out, because check-run
identity derives from it and D4's six-checks clause depends on that identity: a
renamed job is a behavioural change even when the new name is a translation of
the old. And **shell structure outside the quotes** is out, including
`>> "$GITHUB_OUTPUT"` and the key side of any `key=value` written to one —
`echo "tag=${tag} built version=${built}"` is a log line and is prose; the same
string with a redirection after it is an interface another step reads.

The clause ships as a script and not as the paragraph above because the
paragraph is not enough. On ZED-84 the CEO re-read PR #61 rather than take its
summary, and the summary had already drifted: the workflow half changed four
`run:`-block lines across two files, not the "one `echo`" it claimed, and one of
them was a `::error::` command on the publish path. The conclusion survived, but
a careful agent's eyeball classification had miscounted the diff on the easiest
possible case. That is the whole argument for an exit code.

**C2 — a static witness that actually reads the file.** Pinned `actionlint`, in
the same container as the matrix, on both `origin/master` and the pull request
head; the head must introduce **no finding master does not already carry**.

```bash
./scripts/actionlint-differential.sh origin/master my-branch
```

This clause is what earns the refinement. The matrix of D6 is a
*reimplementation* of `ci.yml` and therefore witnesses the workflow not at all,
while actionlint parses it, and its shellcheck pass covers the one way a
translation really breaks a workflow: quoting damage inside a string it
rewrote — an apostrophe in "didn't", a backtick, a bare `$`. The division of
labour was checked rather than assumed. A backtick injected into one of #61's
own translated log lines passes C1, which is correct (it is text inside a quoted
string), and C2 refuses it as `SC2006`.

**Differential, never absolute.** An absolute "actionlint clean" gate would be
the D4 six-checks mistake over again — unsatisfiable through no fault of the
pull request. It is not hypothetical: `master` carries one actionlint finding
today (`SC2012` in `release.yml`), so an absolute gate would refuse every
workflow PR until someone unrelated fixed it. Findings are matched on file, rule
and message, and never on line number, because a prose change moves every line
below it.

**C3 — full D6 evidence for the rest of the pull request.** Unchanged from D6:
`./scripts/docker-matrix.sh`, a Linux container, all three interpreters, the
whole suite, `FORGE_REQUIRE_TOOLS=1`, the validators present, `verify_pins`
passing, and the result recorded on the pull request's issue.

**C4 — `verify_pins` re-run on `master` after the merge.** One command
(`./scripts/docker-matrix.sh --verify-pins-only`), and it closes the loop on the
only file the matrix declares twice.

### What this is not

D7 is **not a thaw**. It is a test with an exit code, and three of the four pull
requests parked under D6 fail it on the first clause — checked, not assumed:
#59 on `on:` and `concurrency:`, #50 on `with:` (and caching is named in D6's
own rationale), #49 on several at once. A container cannot vouch for any of
those and nothing here pretends otherwise.

Neither the scripts nor this entry touches `.github/workflows/**`, so both
merged under plain D6. There is no bootstrap problem.

### Expiry

**D7 is spent when D6 is spent.** It is a refinement of a workaround, not a new
standard: when ZED-66 resolves, six green checks are the evidence again and both
decisions lapse together.

---

## D8 — JARVIS may merge on a local Docker run of its own CI

- **Date**: 2026-10-09
- **Decided by**: the CEO, on issue ZED-87. Recorded by engineering on ZED-89.
- **Repository**: `Zedzed75/JARVIS`, not this one.

D6 does **not** extend to JARVIS, and was not stretched to cover it. Every
operative clause of D6 is forge: `scripts/docker-matrix.sh`, three interpreters,
`FORGE_REQUIRE_TOOLS=1`, the five domains' validator binaries, and a rationale
resting on forge's own commits `223cae4` and `f050a05`. Read verbatim against
JARVIS it is unsatisfiable rather than permissive — there is no
`docker-matrix.sh` there and no 3.11/3.13 leg to run. What ports is the
principle, *change the host, not the standard*, and D8 is that principle written
for the repository it now applies to.

While Actions assigns no runner (ZED-66 — the same account-level billing failure,
JARVIS's last successful run 2026-10-08 15:24Z), a JARVIS pull request **may
merge on evidence from a local Docker run of `ci.yml`'s jobs** instead of on
green checks, provided:

- the container is **pinned to the versions `.github/workflows/ci.yml` pins**,
- `integration` runs against a **real `pgvector/pgvector:pg16`**,
- a **green baseline on plain `master`** is taken first, so that any red is
  interpretable rather than ambiguous between the change and the host,
- **a skipped check is not a passed check** — in particular the backup/restore
  roundtrip must be observed to *run*,
- the result is **recorded on the pull request's issue**,
- and the evidence **binds to the head SHA it was produced on**. If a PR's head
  moves, the run is re-done. Evidence from an earlier head is not evidence for a
  later one.

The baseline clause is not ceremony. It earned itself on the first run: on the
host toolchain (ruff 0.14.10, Python 3.13) JARVIS's own `master` fails
`ruff format --check`, so a formatting complaint from a host-run suite is version
noise and would have been read as a defect in whichever PR was under test.

### The exception, behavioural and not file-path

A pull request touching **`Dockerfile`, `pyproject.toml`, `poetry.lock` or
`.github/workflows/**`** may not use this path. Those are the inputs a local
suite cannot vouch for: the suite consumes the pins rather than testing them, so
a change *to* the pins is tested by nothing. This is the same refinement D7 made
to D6 — the exception protects behaviours, and these four are named because each
one is an input to the evidence rather than a subject of it.

If such a pull request must still move, a local **`docker build` of the image is
required additional evidence** — that is the local substitute for the *build*
half of `build-and-push`. The push, retag and retention half needs no substitute
while nothing deploys.

### `build-and-push` is deferred, not waived

Merges under D8 land with **no image built** until Actions returns. That was
checked rather than weighed, and the objection comes apart in three places:

1. **Merging cannot regress the live service.** `build-and-push` pushes to GHCR;
   it does not deploy. JARVIS deploys by a deliberate
   `terraform apply -var-file=...` with `variable "image"` (default
   `jarvis:dev`), consumed at `terraform/app.tf:40` and `terraform/telegram.tf:48`.
   `master` and the running pods are decoupled by an explicit pinned ref, so with
   Actions down `latest` keeps pointing at the 8 Oct digest and nothing pulls
   anything new. The outage insulates the service rather than endangering it.
2. **The retention gap fails safe.** `cleanup-old-images` is
   `min-versions-to-keep: 3`. Not running means images **accumulate**, not
   vanish — registry housekeeping, self-correcting on its next run, not a gate.
3. **For the PRs this unparked, the image build had no coverage to add.** None of
   the six ZED-33 branches touches `Dockerfile`, `.github/**`, `pyproject.toml`
   or `poetry.lock`; and the `Dockerfile` resolves dependencies solely from those
   pins, then plain-`COPY`s `jarvis/`, `config/`, `web/` — no compile, no
   bundling, nothing executed at build time.

Reason 1 is what makes D8 safe where it would not be in a repository that
deploys on merge. It is a property of JARVIS's deployment, not a general
dispensation, and a change to that property retires this decision early.

### Expiry

D8 is **in force until Actions runs again**. When ZED-66 resolves, the green
checks are the evidence again and D8 is spent. ZED-91 tracks the one thing that
must then be confirmed rather than assumed: that the image pipeline actually
caught up on the commits that landed without it.
