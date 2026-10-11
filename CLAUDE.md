# Project: forge
Plugin-based deterministic generator of complete, commented IaC projects from a
single service spec. Built by porting the legacy standalone tools in _legacy/
(read-only reference; never import from it).

## Target architecture (from the original brief — five plugins, not two)
**Status**: all five domains shipped. `pipeline` was parked on a branch during the
consolidation of the first four, then finished and merged back — it is the only
domain whose output depends on the other sections, and the only one whose output
is the repository root.
```
forge/
├── core/          # shared: spec model, Jinja2 engine (custom delimiters),
│                  # golden tests, CLI verbs, validation runner
├── plugins/
│   ├── ansible/   # templates + spec section + validators (ansible-lint, syntax-check)
│   ├── helm/      # templates + spec section + validators (helm lint, kubeconform)
│   ├── terraform/
│   ├── pipeline/
│   └── monitoring/
```
Ansible and Helm are the only ones with legacy code to port; the other three are
written from scratch. **The domains are a choice, never a package**: a section
absent from forge.yml generates nothing, `--only` restricts a run, and the
interview asks which domains to generate. Producing an Ansible project *and* a
Helm chart together is one possible use, not the normal one.

## Hard rules
- Core is domain-agnostic. Domain knowledge lives only in plugins/<domain>/.
- Rendering and updates go through copier (library mode). Never hand-roll rendering.
- Anything the renderer reads must reach the wheel: under `src/forge/`, or in the
  `force-include` table of `pyproject.toml`. The template root is the repo root from a
  checkout and `site-packages/forge/` from an install (DESIGN.md §8 Q2-bis). Get this
  wrong and an installed forge cannot generate while every test still passes — they all
  run from a checkout.
- Plugin contract via pluggy hooks. Adding a domain must not require touching core.
- Same spec => same generated output. Golden tests enforce it.
- Every generated file is commented: header explaining its purpose, explicit names on
  tasks/resources, a comment on every user-facing variable (usage + allowed values).
- Generated projects must pass their plugin's validators (ansible-lint + syntax-check
  for Ansible; helm lint + helm template + kubeconform -strict for Helm).
- FQCN only for Ansible modules; Helm best practices (helpers, app.kubernetes.io labels,
  no hardcoded values). Never invent a module or resource kind.
- **English throughout**: comments, docstrings, prose, documentation, identifiers, keys
  and file names — in this repository and in everything it generates. This reverses the
  original rule ("comments/docs in French"), under which every existing file was written;
  a file still carrying French is awaiting translation, never a pattern to copy.
  (Decision D3, DECISIONS.md.)
- Standing policy decisions are numbered D1, D2, … in **DECISIONS.md** — the published
  package name, the language rule, and what engineering merges without a confirmation
  card. Read it before asking the board to confirm anything: D4 and its three carve-outs
  say exactly which changes still need a card. DESIGN.md §8 is the other register —
  technical arbitrations (Q1 …), not policy.
- ALL plugin templates use copier custom delimiters [[ ]] / [% %] / [# #] (decision Q1,
  DESIGN.md §8): Helm's {{ }} and Ansible's {{ }} both pass through untouched. One root
  copier.yml, so one set of delimiters. Never write {{ }} meaning "generator variable".
- `_legacy/` **is gone** (deleted in phase 10, with the parity snapshots and their
  tests). MIGRATION.md is what remains of it: the merged duplicates, the
  arbitrations, the assumed divergences. There is nothing left to re-read.

## Token economy (important)
- Read PLAN.md (and MIGRATION.md when porting) at session start; work on exactly one
  phase; update PLAN.md; commit; stop.
- Audit _legacy/ selectively: directory tree first, then only the spec model, CLI entry,
  2-3 representative templates and the test harness of each tool. Never read it wholesale.
- Never print full generated trees or large diffs in chat. Run the test suite and report
  a summary (pass/fail + first failure) instead of pasting output.
- Rely on golden tests rather than re-reading generated files to check results.
- Do not read third-party package sources unless debugging a specific failure.
- Prefer many small template files and surgical edits over rewriting big files.

## The shared checkout: read through a ref, not through the working tree
`Z:/vm/zedux/partage/repo/forge` is the shared primary checkout; dozens of worktrees hang
off it. Nothing mechanical can enforce the rules below — `git grep` is not hookable, and a
test asserting "HEAD is master" would fail in every worktree — so they are conventions, and
the last one is the one that holds even when the others have been broken.
- **Keep it on `master`.** Never `git checkout` a topic branch there; add a worktree
  instead (`git worktree add C:/t/wt-<issue> -b <branch> origin/master`). Branch-agnostic
  commands — `git fetch`, `git worktree add`, `gh` — are safe in the primary checkout.
- **Reading the working tree is not branch-agnostic.** A plain `git grep <pattern>` answers
  about whatever is checked out, and the answer looks just as confident when it is wrong.
  Running the suite there tests that tree too, and forge's gates read data files from it
  (`tests/french_baseline.txt` is one).
- **A clean `master` is still not a current `master`.** The local ref answers about the last
  fetch, not about the remote.
- **So when the question is "is this still on `master`?", read through an explicit ref after
  a `git fetch`**: `git grep <pattern> origin/master -- <path>`, `git ls-tree`,
  `git show <sha> -- <path>`. Use the `-- <path>` pathspec form rather than `git show
  <ref>:<path>`, which MSYS mangles on Windows. This is the habit that survives a drifted
  checkout, so prefer it even when `HEAD` looks right.

(ZED-209 is why: the checkout sat 17 days on a topic branch *and* its local `master` was 40
commits behind. Neither is visible in a grep's output.)
