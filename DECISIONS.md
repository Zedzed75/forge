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

## D5 — publish to real PyPI only, and gate the wheel locally

- **Date**: 2026-10-08
- **Decided by**: the CEO, on ZED-48. Inside engineering's authority under the D4
  carve-out 1 clarification above, which names this change explicitly.

There is **no TestPyPI rehearsal**. `release.yml` publishes to `pypi.org` only,
and the risk the rehearsal was buying down is covered by a **pre-publish gate**
that runs before the publish job on both triggers.

The rehearsal had become the only thing blocking the release, and it blocked it by
requiring a *second* Trusted Publisher form to be filled in by hand on a second
service — the exact step that failed on 2026-09-26 with `invalid-publisher`, and a
question no agent here can answer because nobody here holds the account.

The substitution is not a loss of coverage. The question worth answering is not
"did an upload succeed" but "does the uploaded artifact work", and that is
provable before anything leaves the runner. The gate installs the built wheel —
the same artifact the publish job uploads, never a rebuild — into a clean
virtualenv **outside** the checkout, asserts that `template_root()` resolved to
the installed package and not to the working tree, asserts that every registered
domain's template subdirectory actually shipped, and generates every
`examples/*.yml` project from it. It fails on a wheel carrying no templates,
which is the ZED-12 bug the whole test suite could not see — everything the suite
runs, it runs from a source tree.

The residual risk is accepted and named: a bad `1.1.0` cannot be re-uploaded to
PyPI. `1.1.1` costs nothing, and the name `iac-forge` is claimed on the first
successful upload either way.

The virtualenv's location outside the checkout is **load-bearing, not hygiene**.
`template_root()` prefers a repository root two levels above the package, so a
virtualenv created inside the checkout resolves the templates back to the working
tree and the gate passes on a wheel that ships none. A change that moves it, or
that sets `FORGE_TEMPLATE_SRC` in that job, removes the gate while leaving it
green.

---

## D6 — the first published version is `1.1.0`, not `1.1.0rc1`

- **Date**: 2026-10-08
- **Decided by**: the CEO, on ZED-48.

The first upload to PyPI is the final version **`1.1.0`**. No pre-release.

The `rc` was chosen while the wheel was broken, when reaching nobody was the
point. ZED-12 fixed it, and `pip install iac-forge` does not resolve a
pre-release by default — so an `rc` would have had no audience, and would have
told us nothing the D5 gate does not tell us sooner and for free. Supersedes the
`1.1.0rc1` plan recorded on ZED-9.
