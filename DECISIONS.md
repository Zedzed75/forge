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
