# DECISIONS.md — standing decisions

Standing policy decisions, numbered `D1`, `D2`, … Each one is in force until a
later decision recorded here replaces it. They are **policy**: what engineering
may do, what the board decides, what a given name or language is. The technical
arbitrations of the architecture (`Q1` … `Q9` — delimiters, `copier.yml` layout,
inter-domain checks) are a different thing and live in `DESIGN.md` §8.

Where a decision is cited in an issue thread, the issue is linked below as the
origin of the ruling; **this file holds the text**, because issues close. Nothing
else may hold a copy of it — that is D13, and it is the rule this preamble was
previously vague about.

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

The host the container stands in for is **`ubuntu-24.04`** — which is what
`ubuntu-latest` resolved to when this decision was taken, and what
`scripts/docker/Dockerfile.ci-matrix` pins. It is deliberately not "whatever
`ubuntu-latest` means today": from 2026-10-19 that label begins a staged
migration to Ubuntu 26.04, completing 2026-11-19
(`actions/runner-images#14748`). D6's evidence does not weaken on that date —
the nine pinned versions still have to match `ci.yml` verbatim, `--verify-pins`
still fails the run on drift, and `FORGE_REQUIRE_TOOLS=1` still refuses a run
with a validator missing. What would decay is the *wording*, if equivalence were
stated against a label that moves. So it is stated against the version, and
D10 requires the workflows to name that version too.

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
  later one. **This clause is not the whole of the requirement: D17 amends it to
  bind the base as well.** Read D17 before concluding that a green head-bound run
  is enough.

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

### Expiry — amended by D11, and not a stopgap

**The original wording of this section is superseded.** It read: *"D8 is in
force until Actions runs again. When ZED-66 resolves, the green checks are the
evidence again and D8 is spent."* That named a condition and an event as though
they were one thing, they came apart, and **D11 replaces it**. The sentence is
quoted here once, as the thing that was wrong, and must not be cited as the
rule — it is the sentence a stale copy in `JARVIS/MEMORY.md` went on serving
until ZED-140 removed it.

So D8 is JARVIS's **standing** evidence path, not a stopgap: it holds until
JARVIS's own checks actually run, which is neither a date nor an event in
another repository. **D11 clause 2 is the operative text** and the review it
schedules is a review, not an expiry. Wording settled by the CEO's ruling on
ZED-135 §3; recorded on ZED-140.

ZED-91 tracks the one thing that must be confirmed rather than assumed when
JARVIS's checks do return: that the image pipeline actually caught up on the
commits that landed without it.

---

## D9 — a merge authorisation names its pull requests, and is a ceiling

- **Date**: 2026-10-09
- **Decided by**: the CEO, on issue ZED-92, raised by the CTO from ZED-90. Recorded by
  engineering on ZED-93.
- **Scope**: both repositories. Clause 4 is JARVIS-only and expires with D8.
- **Clarified**: 2026-10-10 by engineering on ZED-181 — clause 4 reads on *permission*, not on
  concurrency; see *Clause 4 is about who may merge, not who is running* below. The four clauses
  themselves are unchanged.

The preamble to this file already says that *a decision is not a grant for anything it does not
name*. It says it about evidence standards, next to D4. ZED-89 shows the same sentence is needed
about **authority**: an issue scoped to "the four ready ZED-33 PRs" merged those four and then two
more — #298 and #290 — which ZED-90 existed to hold back until head-bound D8 evidence covered
them. Nothing was lost, because ZED-90 re-derived both resolutions independently and they matched.
But the gate was walked past, and it held only because two runs happened to agree.

1. **Named.** An authorisation to merge names its pull requests by number — "#291, #292, #294,
   #295". A count does not say which, and "the ready ones" is not an authorisation: it delegates
   the choice of set to whoever reads it, at the moment when readiness is exactly what is in
   dispute.

2. **A ceiling, not a floor.** The named set is the whole of the authority. A pull request that is
   not named is not authorised, and no observation made during execution adds one — not "it is
   also green", not "it is also CLEAN", not "it was obviously intended". If more should merge, the
   authorising issue is amended or another issue is filed. This is the operative clause, because
   it is the only one that does not depend on the ticket's author having anticipated the overlap.

3. **Singly held.** No two open issues hold merge authority over the same pull request. Where one
   batch is split across sibling issues, each names its own pull requests, each says which sibling
   holds the rest, and the ordering is a `blockedByIssueIds` edge — not timing, and not the order
   the runs happen to start in.

4. **While D8 is in force, clause 3 is per repository for JARVIS.** One issue at a time holds
   JARVIS merge authority. D8 evidence binds to a head SHA; a concurrent merger moves `master` and
   invalidates it. This is the mechanism that rejected ZED-90's push twice, and it costs nothing to
   serialise JARVIS while nothing else may merge anyway. The clause **retires with D8**: once
   required checks run on the head again, GitHub serialises on the head by itself and clause 3
   reverts to per-pull-request.

### Clause 4 is about who may merge, not who is running

Holding JARVIS merge authority means being **permitted to merge**. A live sibling run, an open
non-draft pull request, or an `in_progress` issue touching the same repository does not hold the
slot. An issue whose pull request is barred by D8's exception list, or that no authorisation
names, holds nothing to contend with — and the ordering edge of clause 3 applies to one batch
split across siblings, not to independent fixes that merely share a repository.

Read that way, whether the slot is held is an observable fact about the authorisations in force
and the pull requests they name — four `gh` calls, not a question anybody has to be asked. Two
round trips in one day went the other way, both on this text as written, which is why this is a
ledger change and not a correction to anybody:

- **ZED-173** read clause 4 as something only the CEO could answer. Answered on ZED-177, which
  also records that a single pull request raised from its own fix issue needs no grant card.
- **ZED-179** surveyed correctly and then read "a sibling is running" as "the slot is held",
  proposing an ordering edge from a `MERGEABLE` authorised pull request to a sibling whose own
  pull request D8's exception list forbids merging at all. The edge would have parked the
  authorised one until JARVIS Actions return, behind something that could not move. Overruled on
  ZED-177.

**D17 narrows what clause 4 is needed for.** Clause 4's rationale is that a concurrent merger
moves `master` and invalidates head-bound evidence; D17 answers a moved base directly, with a run
of the merge-result tree. D17 says clause 4 "is necessary and is not sufficient" for that; the
converse is worth saying too — it is not to be *reached for* either. Base divergence is D17's
clause to apply, so clause 4 does not grow into a general bar on sibling work by being the
nearest clause to hand. What it bars is a second authorisation over the same pull request. It
says nothing about who is running.

### The ZED-33 merges stand

No rework. All six pull requests are in, `master` is green, and the run on `master 78b8736` is
tree-identical to #290's merged head, so D8's head-binding holds retroactively. That is
ratification of one outcome on examined evidence — ZED-90 re-derived both forward-merges without
reading ZED-89's, and forced the time-dependent briefing test with `faketime` against the pre-fix
head to prove the instrument catches the defect. It is **not** a precedent that evidence may follow
a merge. Under D8 the run comes first; where it did not, it was checked afterwards by an agent who
could have found a defect and would have reported one.

---

## D10 — the runner label is pinned, not floating

- **Date**: 2026-10-09
- **Decided by**: **engineering (the CTO)** — not the CEO. Taken under the authority the CEO
  delegated on issue ZED-72, AC #3: *"Pinning trades automatic currency for a controlled
  upgrade; given that CI is our only real validation environment, I lean toward pinning, but
  engineering owns the call."* Recorded by engineering on ZED-100. Every other record in this
  file is a CEO decision; this one is engineering's, and must not be cited as the board's.
- **Scope**: this repository's own workflows. Generated output is **not** covered — see "What
  this does not decide".

`runs-on` names an explicit Ubuntu label — `ubuntu-24.04` — in every workflow under
`.github/workflows/`. It does not name `ubuntu-latest`.

CI is forge's only authoritative validation environment. That is not a preference, it is
DESIGN.md §8 Q7's finding: `ansible-core` does not support Windows as a control node, and
`kubeconform`, `promtool` and `tflint` ship as Linux binaries, so "the GitHub CI (Linux)
remains the authority". A floating label means that single authority moves underneath the
repository on GitHub's schedule rather than on a reviewed commit.

From 2026-10-19 `ubuntu-latest` begins a staged migration to Ubuntu 26.04, completing
2026-11-19 (`actions/runner-images#14748`). The *staged* part is the sharp edge: during the
window the same commit is green on one run and red on the next with nothing in the repository
having moved, and a re-run that disagrees with its predecessor is indistinguishable from
flake. This repository has already paid for that failure class twice, arriving from a package
index instead of a base image:

- `528b3c7` — `community.postgresql` 5.0.0 removed `postgresql_set`, and the collection was
  unpinned.
- `a830c6d` — the Ansible validators were unpinned, and they drifted.

Both fixes were pins. The base image is the same bet with a wider blast radius, because it
moves every preinstalled tool at once rather than one collection.

### The cost

Automatic currency is given up, and that is a real loss, not a rhetorical one. A pinned label
does not pick up a newer runner image, a security update to a preinstalled tool, or the next
LTS by itself. Somebody has to do it on purpose, and if nobody does, nothing complains. That
is the trade the delegation named, taken with the trade understood.

The pin is also itself temporary. Superseded `ubuntu-*` labels have historically been retired
roughly a year after the promotion completes, so `ubuntu-24.04` will eventually stop
resolving — loudly, and at a time of GitHub's choosing rather than ours. D10 therefore
obliges a **deliberate, dated upgrade**, not an indefinite freeze: the move to
`ubuntu-26.04` is proven by a canary job running the suite on the new label *before* the
pinned label changes, so the upgrade arrives as a reviewed diff carrying evidence. A pin left
unexamined until the label dies is the same failure D10 was taken to prevent, wearing the
other face.

### What this does not decide

Generated output. The pipeline domain's `runner` is a **spec field**
(`PipelineSpec.runner`, defaulted per provider and rendered into `runs-on`), and its value is
the user's choice — someone generating for their own fleet may legitimately want a
self-hosted label, or a floating one. D10 is a rule about how forge validates forge. It is
not a rule about what forge emits, and a later reader must not infer one from it.

### Implementation is not in this record's commit

`runs-on` lives under `.github/workflows/**`, which D6's exception and D7's script both keep
outside the Docker evidence path — so the workflow edit cannot merge on a container run, and
this record does not carry it. It lands on ZED-99 (pin `runs-on` to `ubuntu-24.04`, add an
`ubuntu-26.04` canary) as the first pull request merged once ZED-66 clears. Until then the
decision stands recorded while the workflows still say `ubuntu-latest`: the gap is known,
dated, and owned by ZED-99 rather than discovered later.

**Both halves have now landed, in two pull requests rather than one.** ZED-99 shipped the pin
(#80). The canary came apart from it because a canary must be a **second job** — a
`matrix.include` entry carrying a `runner` key does not create a fourth combination, it merges
into the matching existing one, which moved the gating 3.13 leg onto 26.04 and un-gated it
while all six checks still reported green. It landed on ZED-119 instead, together with the
extraction of the install steps into `.github/actions/forge-ci-setup/action.yml` that letting
two jobs share one toolchain required.

### The canary is not one of D4's six checks

D4 authorises a merge on a count: "CI-green on all six checks". The canary adds a fourth
check-run per event without touching that count, and the mechanism is `continue-on-error:
true` at job level. What that flag actually does was **measured, not read** — a deliberately
failing canary was pushed on a throwaway branch — because the whole reason this canary needed
a second attempt is that the first one was believed rather than checked:

| | when the canary fails |
| --- | --- |
| workflow **run** conclusion | `success` |
| the canary **job** conclusion | `failure` |
| its **check-run** conclusion | `failure` |

The flag makes the *run* green, not the *check*. That is the right way round — an advisory job
that went green on failure would advise nothing — but it means the canary is red in
`gh pr checks` while the merge standard is satisfied, which is a disagreement a reader has to
be told about rather than left to resolve. So:

- the three gating legs keep the names and the runner D4's clause counts: `tests (3.11)`,
  `tests (3.12)`, `tests (3.13)`, on `ubuntu-24.04`;
- `canary (3.13, ubuntu-26.04)` is advisory, and **a red canary does not withhold a merge**;
- nobody needs to re-read D4. This is engineering recording how its own decision was
  implemented so as not to disturb the board's, which is the reason the rejected alternative
  was rejected: a real `runner:` matrix axis costs six lines and renames every check-run to
  `tests (3.11, ubuntu-24.04)`, i.e. renames the things D4 counts in order to save a file.

The reading that needs stating out loud, because the arithmetic invites the other one: D4's
"six" is six *gating* checks, and it always was. A seventh and eighth check-run that cannot
fail the workflow do not make it seven or eight.

The operational corollary, for whoever next automates a merge-readiness poll: **do not wait for
every check-run to be green.** On a red canary that wait never ends, and D4 is satisfied
anyway. Wait on the three `tests` legs by name, or on the workflow run's conclusion.

### Expiry

D10 does not expire when the pin lands — the standing rule is that the label is explicit.
What expires is the **value**. Review it at whichever comes first: `ubuntu-26.04` generally
available on GitHub-hosted runners, or GitHub announcing retirement of the `ubuntu-24.04`
label. At that review the canary is the evidence and the pin moves forward in its own commit.

**The first trigger has already fired, earlier than this record guessed.** It said "expected
after 2026-11-19"; `ubuntu-26.04` and `ubuntu-26.04-arm` went generally available with
`actions/runner-images#14747`, *before* the `ubuntu-latest` migration window opens on
2026-10-19. That is why the canary could be built and run on 2026-10-09 rather than waited
for. It does not move the pin by itself — D10 requires the pin to move as a reviewed diff
carrying the canary's evidence, and one green canary run is a reading rather than a record.
The review belongs to ZED-72, which owns the upgrade and is where the canary's results are
recorded.

---

## D11 — D8's expiry is evaluated per repository

- **Date**: 2026-10-09
- **Decided by**: the CEO, on issue ZED-109, raised by the CTO from ZED-91. Recorded by
  engineering on ZED-110.
- **Scope**: amends D8.

D8 said it was "in force until Actions runs again. When ZED-66 resolves, the green checks are
the evidence again and D8 is spent." That names a condition and an event as if they were the
same thing, and they came apart: ZED-66 resolved on `forge` evidence, while `Zedzed75/JARVIS`
is still private and behind the unpaid-minutes gate. Read literally, D8 self-terminated for a
repository whose checks still do not run — leaving JARVIS merges with no authorised evidence
path. The defect is in D8's wording, not in anyone's conduct.

1. **Spent for `forge`**, effective 2026-10-09 07:31 when ZED-66 closed. `forge` is public,
   Actions runs, head-bound green checks are the evidence again.

2. **In force for `Zedzed75/JARVIS`**, and *not* spent by ZED-66. Expiry is evaluated **per
   repository, on whether that repository's own checks actually run** — never on a shared event
   id. While that holds, this is JARVIS's **standing** evidence path and not a stopgap awaiting
   a date: the only thing that ends it is JARVIS's own checks running. *(Wording settled by the
   CEO's ruling on ZED-135 §3 and amended here on ZED-140: the clause was correct and read as
   temporary, which is how ZED-135 came to re-litigate a decision that was already made.)*

3. **Retroactively affirmed:** JARVIS merges made on the local-Docker path between ZED-66
   closing and this amendment were authorised.

4. **A runner-image narrowing needs no evidence where CI cannot start.** A change whose *only*
   effect is to narrow `runs-on` (e.g. `ubuntu-latest` → `ubuntu-24.04`) is admissible under D8
   without a run: it is strictly more conservative than floating, and on a repository where no
   job starts there is no behaviour to regress and no evidence obtainable. This is not a general
   licence for `.github/workflows/**` edits, and it lapses with clause 2.

### Why JARVIS stays private

Paying is closed by standing board policy (the `be5bdb45` rejection: the board is not paying
for CI). Publishing JARVIS is *not* the decision taken for `forge`: `forge` going public
advanced a stated goal (ZED-2, D1), whereas JARVIS is private personal infrastructure and
publication would be a new irreversible exposure. It would buy only GHCR images that nothing
consumes — the cluster runs the local `jarvis:dev` tag by design
(`terraform/environments/dev.tfvars:4`), never GHCR.

### Review on trigger or date — a review, not an expiry

If image publication becomes load-bearing — deploys move to GHCR, or anything outside the
cluster needs the image — JARVIS-public goes to the board as its own decision, with a full
history sweep first. Otherwise clause 2 is **re-examined** by **19 November**, when the Ubuntu
runner rollout completes.

That date is when somebody looks, not when the clause lapses. If JARVIS's checks still do not
run on 19 November, clause 2 continues unchanged and needs no renewal; the date exists so that
a standing arrangement is not left unexamined, which is D10's lesson about an unexamined pin
applied to a standing permission.

---

## D12 — an unavailable capability degrades to a refusal, never to an answer

- **Date**: 2026-10-09
- **Decided by**: the CEO, on issue ZED-122, from the ZED-114 finding. Recorded by engineering
  on ZED-124.
- **Scope**: JARVIS, and any future assistant surface. Standing.

With `meteo_france_enabled` false, `get_weather_alerts` was never registered as a tool, so the
supervisor answered a weather-vigilance question from the model alone: *"Non, le Rhône est
actuellement en vigilance verte, sans alerte particulière."* That was fabricated, and it is
indistinguishable from a genuine all-clear — the exact sentence a user would act on during an
orange or red alert.

1. **When a capability is unavailable, the assistant says it cannot check.** It does not answer
   from the model alone, and it does not reassure.

2. **Implement the refusal as a registered stub tool**, not as prompt text. The cause was that
   no tool existed, so the model answered unaided; a tool whose return value *is* the refusal
   fixes the cause rather than one phrasing.

3. **Every capability gated behind an `*_enabled` flag needs a refusal stub on its off-path.**
   A flag that silently unregisters a tool is a latent fabrication, not a clean disable.

**The trade, accepted explicitly:** a JARVIS that often says "I cannot check that" is preferred
to one that is occasionally confidently wrong about a safety signal. A reminder that does not
fire is visible; a fabricated all-clear is invisible, and worse.

The code fix and the integration-wide audit of `*_enabled` flags are ZED-114 and ZED-122; this
entry is the durable record of the rule they implement.

---

## D13 — reference, do not restate

- **Date**: 2026-10-09
- **Decided by**: the CEO, in the ruling on issue ZED-135 §2 — *"reference, do not restate. A
  decision's text lives in one place."* Whether that became a numbered entry was left to
  engineering on ZED-140; engineering records it, because the alternative is a standing rule
  whose only copy lives inside a closed issue, which is the failure the rule describes.
- **Scope**: both repositories, and every document that is not this file. Standing.

A decision's operative text lives in **exactly one place: this file**. Any other document may
name a decision, say **that** it applies, and link here. It may not reproduce **what it says** —
its conditions, its carve-outs, its thresholds or its expiry.

### What this forbids, and what it does not

- **Forbidden: a second copy of a clause a reader acts on.** `JARVIS/MEMORY.md` §4 carried
  *"D8 is spent as soon as Actions runs again"* — D8's pre-D11 expiry, reproduced in the file
  JARVIS work is actually read from first. D11 amended the ledger, the copy did not move, and
  ZED-135 re-escalated a settled decision from the stale sentence. The copy that goes stale is
  the one people read, because it is the one far away from the amendment.
- **Allowed: a pointer.** *"D8 governs merges in this repository; the terms are in
  `forge/DECISIONS.md`."* A pointer cannot diverge, and it is strictly more useful than a
  summary, because it cannot be trusted in place of the thing.
- **Allowed: how to *satisfy* a decision, in terms of a document's own artifacts.**
  `CONTRIBUTING.md` documents `scripts/docker-matrix.sh` and
  `scripts/workflow-diff-is-prose.sh` — the command, the exit codes, how the witness works —
  and sends the reader here for the clause each one implements. A script is not a restatement
  of a clause; under D7 the script *is* the clause, which is the whole reason D7 shipped as an
  exit code.
- **Allowed: this file quoting its own superseded wording,** marked as superseded. D8's expiry
  section does exactly that. The history of a clause belongs next to the clause, and nowhere
  else.
- **Not covered: a rule this file records a *change to* rather than owns.** D3 reversed
  `CLAUDE.md`'s language rule; `CLAUDE.md` is where that rule is read and obeyed, and the
  bullet *is* D3's subject. Moving it out would leave the instruction file silent about the
  instruction. The test is whose text it is: `CLAUDE.md` owns the rule and D3 records the board
  changing it, so that bullet is not a second copy of D3 and does not become one by citing it.

### Why this is numbered rather than left as a note

It is the second governance round trip caused by text being in the wrong place, and the two are
mirror images. D4 sat inside ZED-47's thread until it was recorded here, and ZED-52 had to
ratify it to establish what it said — authority with no durable text. ZED-135 is the same
failure the other way round: the text was here, and the divergent copy elsewhere was the one
that got read. One rule covers both, and it is of a kind with D5 — D5 forbids a board state
that names nothing able to end it, D13 forbids a rule whose authority is ambiguous because
there are two of it.

### Enforcement is a grep, deliberately

The restatements this entry retired were found by grepping both repositories for `\bD[0-9]+\b`
and reading every hit. That is the whole mechanism, and there is no script on purpose: the
dangerous form is a *paraphrase* that no longer matches the clause, which is exactly what a
string comparison cannot see and a reader can. Run it when a decision is amended — the
amendment is the moment a copy becomes wrong — not on every pull request.

What that grep found on 2026-10-09, besides `MEMORY.md` §4: one restatement of D8's clause list
in `JARVIS/docs/ROADMAP.md`, and two of D7's clause C1 in `forge/CONTRIBUTING.md`. All three
were converted to references on ZED-140. Every other hit in either repository was already a
pointer.

---

## D14 — publish to real PyPI only, and gate the wheel locally

- **Date**: 2026-10-08
- **Decided by**: the CEO, on issue ZED-48. Inside engineering's authority under the D4
  carve-out 1 clarification above, which names this change explicitly. Recorded by engineering
  on ZED-48.
- **Scope**: this repository's release path.

**On the number.** ZED-48 and its pull request call this decision **D5**, and the next one D6.
Those were the next free numbers when the issue was written on 8 October. By the time the work
landed, D5 through D13 had been taken by nine other decisions -- D13 arrived on `master` while
this pull request's own checks were running. The numbers here are the
authoritative ones — the issue text is older than the ledger it refers to.

There is **no TestPyPI rehearsal**. `release.yml` publishes to `pypi.org` only, and the risk the
rehearsal was buying down is covered by a **pre-publish gate** that runs before the publish job
on both triggers.

The rehearsal had become the only thing blocking the release, and it blocked it by requiring a
*second* Trusted Publisher form to be filled in by hand on a second service — the exact step that
failed on 2026-09-26 with `invalid-publisher`, and a question no agent here can answer because
nobody here holds the account.

The substitution is not a loss of coverage. The question worth answering is not "did an upload
succeed" but "does the uploaded artifact work", and that is provable before anything leaves the
runner. The gate installs the built wheel — the same artifact the publish job uploads, never a
rebuild — into a clean virtualenv **outside** the checkout, asserts that `template_root()`
resolved to the installed package and not to the working tree, asserts that every registered
domain's template subdirectory actually shipped, and generates every `examples/*.yml` project
from it. It fails on a wheel carrying no templates, which is the ZED-12 bug the whole test suite
could not see — everything the suite runs, it runs from a source tree.

The residual risk is accepted and named: a bad `1.2.0` cannot be re-uploaded to PyPI. `1.2.1`
costs nothing, and the name `iac-forge` is claimed on the first successful upload either way.
(This paragraph named `1.1.0` and `1.1.1` when it was recorded. D16 moved the first published
version to `1.2.0`; the two digits here follow it, and nothing else in D14 does.)

The virtualenv's location outside the checkout is **load-bearing, not hygiene**.
`template_root()` prefers a repository root two levels above the package, so a virtualenv created
inside the checkout resolves the templates back to the working tree and the gate passes on a
wheel that ships none. A change that moves it, or that sets `FORGE_TEMPLATE_SRC` in that job,
removes the gate while leaving it green.

---

## D15 — the first published version is a final version, `1.2.0`, not an `rc`

- **Date**: 2026-10-08. **Amended 2026-10-09** to name `1.2.0`.
- **Decided by**: the CEO, on issue ZED-48. Recorded by engineering on ZED-48. Called **D6**
  there, for the reason given under D14. Amended by the CEO on ZED-142, recorded by engineering
  on ZED-145.
- **Scope**: this repository's first PyPI publication.

The first upload to PyPI is the final version **`1.2.0`**. No pre-release.

The `rc` was chosen while the wheel was broken, when reaching nobody was the point. ZED-12 fixed
it, and `pip install iac-forge` does not resolve a pre-release by default — so an `rc` would have
had no audience, and would have told us nothing the D14 gate does not tell us sooner and for
free. Supersedes the `1.1.0rc1` plan recorded on ZED-9.

**On the digit.** This decision said `1.1.0` when it was recorded, and the number was never
available: `v1.1.0` had been an annotated tag since 31 August, on a porting milestone, and
`release.yml` guards the tag against the built version — so the publish could not have been
triggered under the old number without either moving that tag or breaking the guard. Nothing had
ever been published at the time, so no PyPI version was abandoned and no installed version
changed meaning. What this decision is *about* — a final version rather than an `rc`, and why —
is untouched by the digit. The namespace boundary the new number draws is D16.

---

## D16 — published versions begin at `1.2.0`; a tag is never force-moved to free a number

- **Date**: 2026-10-09
- **Decided by**: the CEO, on issue ZED-142. Recorded by engineering on ZED-145. The last
  clause is a standing rule and is not specific to this repository.
- **Scope**: this repository's version namespace, and — for the last clause — every public
  repository this company owns.

**Published `iac-forge` versions begin at `1.2.0`.** Nothing below it was ever published, and
nothing below it ever will be.

**`v0.1.0` through `v1.1.1` — all eleven — are porting-phase repository milestones, not
published releases.** They were cut between 24 August and 2 September to mark the phases of the
port, at a time when no distribution existed under any name. The top three name themselves
"forge 1.0.0", "forge 1.1.0" and "forge 1.1.1" in their tag subjects, which is what made this
question worth a decision rather than a footnote: read on its own, `v1.1.0` looks exactly like a
release of the thing that is now on PyPI, and it is not one. `pip install iac-forge==1.1.0`
resolves nothing and always will.

**`release.yml` keeps its `v*` trigger.** The collision closes by moving forward, not by
narrowing the trigger: every tag that exists sorts below `v1.2.0`, so the first tag the trigger
can now fire on is the first one we mean it to. The alternative was to edit the trigger or its
tag guard, and that path has just published successfully — it is not worth re-opening to solve a
problem that an increment solves for free.

**Tags on a public repository are never force-moved or deleted to free a version number.** This
is the part that is standing and general. A tag that has been pushed is someone else's reference:
a clone, a `pip install` from git, a submodule pin, an archive URL, a release page. Deleting
`v1.1.0` to re-cut it would have left every one of those resolving to different bytes under the
same name, silently — which is the single failure mode that makes a version number worth
anything. The cost of the rule is that a number can be spent without being published, as
`1.1.0` was here. That cost is one increment. Pay it every time.

**What this forecloses.** Re-deriving the first published version from the tag list, and
proposing a tag rewrite the next time a version number is already taken. Both were considered on
ZED-142 and refused there.

---

## D17 — under D8, evidence binds to the base as well as the head

- **Date**: 2026-10-10
- **Decided by**: the CEO, on issue ZED-168 section D. Recorded by engineering on ZED-170.
- **Scope**: amends D8. JARVIS, for as long as D8 and D11 clause 2 are in force.

**Under D8, evidence binds to the base as well as the head.** A concurrent merge that moves
`master` does not void a head-bound run, but it does require a run of the **merge-result tree**
before merging. The pull request head need not move to satisfy this, and should not be moved
for it.

**The gap this closes is a literal reading that is also a true one.** D8's last clause binds
evidence to the head SHA. On ZED-158, evidence for #326 was produced against base `d0d7ba9`;
#327 merged as `d1f348c` while that run was still going. The head never moved, so the clause was
satisfied exactly as written — and the tree a merge would actually create had never been run
once. Nothing was violated and nothing was proven. That is the shape of the defect: not a rule
broken, a rule that stopped covering the case.

**D9 clause 4 does not already cover it, and it was fair to think it might.** Clause 4
serialises *authority* — one authorisation held at a time — and its rationale even names this
consequence, that "a concurrent merger moves `master` and invalidates it". But serialising who
may merge does not serialise what `master` is: ZED-163 closed at 06:50:13Z, before ZED-168 was
filed, so the authority slot was never doubly held and the bases still diverged. Clause 4 is
necessary and is not sufficient. This entry supplies what it asserted without requiring.

**Re-running the merge-result tree is deliberately cheaper than the alternative.** The
alternative considered was serialising every JARVIS merge behind every other one, which costs a
full suite of latency per pull request in exchange for the same guarantee. One extra run on the
tree you are about to create is the smaller price, and it is paid only when a base actually
moves under you.

**Do not move the head to satisfy this.** Rebasing to refresh the base would invalidate the
head-bound evidence under D8's own clause and buy a second full run, and a force-push rewrites
what reviewers already read. Run the merge-result tree instead and record it; the head stays
where it is.

**What this forecloses.** Reading D8's head-binding clause as the whole of its evidence
requirement, and treating a green head-bound run as sufficient when `master` has moved since it
started. Both were available readings before today, and the first one was taken.
