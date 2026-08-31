# Project: forge
Plugin-based deterministic generator of complete, commented IaC projects from a
single service spec. Built by porting the legacy standalone tools in _legacy/
(read-only reference; never import from it).

## Target architecture (from the original brief — five plugins, not two)
**Status**: four domains shipped — ansible, helm, terraform, monitoring. The fifth
(`pipeline`, CI/CD) was started then parked on the branch `phase-8-pipeline`, at
the user's request, to consolidate the four first. Its commit message carries the
three defects found before it was set aside.
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
- Plugin contract via pluggy hooks. Adding a domain must not require touching core.
- Same spec => same generated output. Golden tests enforce it.
- Every generated file is commented: header explaining its purpose, explicit names on
  tasks/resources, a comment on every user-facing variable (usage + allowed values).
- Generated projects must pass their plugin's validators (ansible-lint + syntax-check
  for Ansible; helm lint + helm template + kubeconform -strict for Helm).
- FQCN only for Ansible modules; Helm best practices (helpers, app.kubernetes.io labels,
  no hardcoded values). Never invent a module or resource kind.
- Comments/docs in French; identifiers, keys and file names in English.
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
