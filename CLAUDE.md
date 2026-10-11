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
  checkout and `site-packages/forge/` from an install (Q2-bis, docs/ARBITRATIONS.md). Get this
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
  say exactly which changes still need a card. **docs/ARBITRATIONS.md** is the other
  register — technical arbitrations (Q1 …), not policy. It was DESIGN.md §8 until D18
  split it out; §8 is now a pointer, so an older citation of "DESIGN.md §8 Qn" still
  resolves, but cite the file.
- ALL plugin templates use copier custom delimiters [[ ]] / [% %] / [# #] (decision Q1,
  docs/ARBITRATIONS.md): Helm's {{ }} and Ansible's {{ }} both pass through untouched. One root
  copier.yml, so one set of delimiters. Never write {{ }} meaning "generator variable".
- `_legacy/` **is gone** (deleted in phase 10, with the parity snapshots and their
  tests). MIGRATION.md is what remains of it: the merged duplicates, the
  arbitrations, the assumed divergences. There is nothing left to re-read.
- **600 lines per file**, warned at 601-700 and failed above 700, enforced by
  `scripts/check_file_sizes.py` as a step of the `tests` job. It sweeps `*.py` under
  `src/` and `tests/`, and the prose registers it names one at a time — not `tests/golden/`,
  which is generated output, and not the community docs. Its `KNOWN_OVERSIZE` table is
  empty and that is the point: the table is a ratchet, not a waiver — an entry that grows
  fails, and an entry that drops under the cap also fails, so ZED-223's two entries had to
  be deleted once their split landed. DECISIONS.md is **exempt** rather than listed (D18:
  an append-only register cited by number), and DESIGN.md is listed and was split instead —
  its §3, §8 and §9 are pointers to docs/FORGE-YML.md, docs/ARBITRATIONS.md and
  docs/REPOSITORY-TREE.md, which are listed too.

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

### Each agent starts in its own home, not in the shared checkout
An agent's working directory is **not** `Z:/vm/zedux/partage/repo/forge`. Each has its own
detached worktree, named after the agent:

| Agent | Home |
| --- | --- |
| CTO | `C:\ah\cto` |
| Senior Coder | `C:\ah\coder` |
| QA | `C:\ah\qa` |
| CEO | `C:\ah\ceo` |

So an unfamiliar `cwd` is the intended setup, not breakage — do not "fix" it by pointing
yourself back at the primary checkout. The paths are short on purpose: forge's generated
trees are long, and a deeper home pushes them past the Windows limit.

- **The homes are detached at a commit, so they go stale.** Refresh with `git fetch && git
  checkout --detach origin/master`. Reading through `origin/master` refs, as above, is
  unaffected by a stale home.
- **A topic branch still belongs in its own worktree** (`git worktree add C:/t/wt-<issue> -b
  <branch> origin/master`), not in your home — the home wants to stay refreshable.
- **Do not `cd` into the primary checkout.** From the Bash tool it retargets the session's
  primary working directory for the rest of the run. Read that tree through a ref instead.

(ZED-221 is why: two agents sharing this directory raced Claude Code's
write-temp-then-rename of `.claude/settings.local.json` and both runs died on Windows
`EPERM`. Measured: 147 failures in 400 renames against one shared destination, 0 in 400
against per-agent ones.)
