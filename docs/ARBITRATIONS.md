# Technical arbitrations — the `Q` register

This file was `DESIGN.md` §8 until ZED-226 split it out: `DESIGN.md` had reached
961 lines, past the 700-line hard cap of `scripts/check_file_sizes.py`, and the
`Q` register was the part of it nobody reads forward. The question identifiers
are unchanged, so an existing citation of "DESIGN.md §8 Q2-bis" resolves here;
§8 itself is now a one-line pointer to this file. The split is recorded as D18
in `DECISIONS.md`.

This file caps itself: it is named in `TRACKED_PROSE` in
`scripts/check_file_sizes.py`, so it warns above 600 lines and fails above 700
like every other register forge wrote.

---

> The eight questions have been settled. Q1, Q5, Q6 and Q7 by an explicit
> answer; Q2, Q3, Q4 and Q8 kept as recommended, without objection. This section
> is from now on a record of decisions: do not reopen it without a new reason.
> Q9 is one, which appeared in production on 2026-09-24 and was arbitrated the
> same day; Q10 and Q11 are others, opened on 2026-10-08. They are added after
> the eight and reopen none of them.
>
> These `Q` entries are the **technical** arbitrations of the architecture. The
> project's standing **policy** decisions — naming, language, what engineering may
> merge without a card — are numbered `D1`, `D2`, … and live in `DECISIONS.md`.

**Q1. Delimiters of the Ansible templates.** The legacy uses `{{ }}` plus
`j()`/`jstr()` helpers and 6 `{% raw %}` blocks to emit Jinja destined for
Ansible. A single `copier.yml` imposes a single set of delimiters.
→ **DECISION: `[[ ]]` for all the plugins.** The Ansible templates then write
`{{ my_variable }}` literally, `j()`/`jstr()` and the `{% raw %}` disappear. A
clear simplification, at the price of a mechanical conversion of the 51
templates in phase 3. *(Alternative: one template repository per plugin, hence
several `copier.yml` — but then no single `_subdirectory` and a heavier
per-plugin update mechanism.)*

**Q2. Template location and `copier update`.** Verified: a `src_path` pointing
at a subdirectory of a git repository is not recognised as a versioned template
→ update impossible.
→ **DECISION: a single `copier.yml` at the forge repository root, with
`_subdirectory` supplied as data.** Validated end to end (copy + update + merge
of a manual edit).
→ **Still in force. Q2-bis adds the installed case it did not cover.**

**Q2-bis. The template root has two shapes, and the repository one wins.**
*(Reopens Q2 — new reason: forge is being published.)* Q2 answered "where does the
template live" for a checkout and, without saying so, made that the only answer.
The repository root does not exist in a wheel, so a `pip install`ed forge found no
`copier.yml`, and `forge generate` refused to generate anything at all. forge had
never been usable from an install. No test saw it: every test runs from a
checkout, where the repository root is there by construction.

The constraint Q2 measured is what makes this awkward. copier treats `src_path` as
a versioned template only when it is the **exact** root of a git repository, and
only a versioned template can be `copier update`d. So the two requirements pull
apart:

- `copier update` from a checkout needs the root to be the **repository root**;
- generating from an install needs the root to be **inside the distribution**,
  and `site-packages/forge` is the root of no repository.

Both were considered. Putting the root inside the package for everyone is the
smaller change and gives one path instead of two — but it takes `copier update`
and the `_commit` line away from *checkout* users as well, not just installed
ones, since `<repo>/src/forge` is no more a repository root than
`site-packages/forge` is. That was judged too expensive: `forge update` is the
reason rendering goes through copier at all.

→ **DECISION: `template_root()` tries the repository root first, then the package
directory.** A checkout and an editable install take branch one and behave
**exactly as before** — versioned template, `vcs_ref="HEAD"`, `_commit` recorded,
`copier update` working, byte-identical output. A wheel install takes branch two.
`copier.yml` and `partials/` stay at the repository root, the one source of truth,
and are **copied into the package at build time** (`force-include` in
`pyproject.toml`) so that both shapes carry them at `<root>/copier.yml` and
`<root>/partials/`. That is what keeps the templates' `partials/header.jinja`
import working unchanged in both: copier roots its Jinja loader at `src_path`.

Two consequences follow, and both are narrow:

1. **A plugin's `template_subdir` is one prefix longer in a checkout than in an
   install** (`src/forge/plugins/ansible/template` against
   `plugins/ansible/template`). Plugins declare the repository form — the one a
   contributor can see on disk — and the core shortens it
   (`copier_runner.resolve_subdir`) by trying both and keeping the one that
   exists. Resolving by probing rather than by remembering which branch was taken
   also makes `FORGE_TEMPLATE_SRC` accept either shape.
2. **An installed forge cannot `copier update`**, and neither can an install-shaped
   `FORGE_TEMPLATE_SRC`. This is copier's constraint, not a gap in forge:
   `site-packages/forge` has no git history to compare against. `run_update`
   refuses with a message that names the *template* root and points at
   `forge generate --force` or at a git clone — copier's own message says
   "git-tracked template" without indicating which of the two repositories it
   means. For the same reason an installed forge records no `_commit` in
   `.copier-answers.yml`; a checkout still does.

Verified against a built wheel and a venv that never had the repository:
`forge/copier.yml` and `forge/partials/header.jinja` are shipped, and
`forge generate` produces a tree identical to the golden one. Both are asserted on
every run by `tests/test_cli.py::test_the_wheel_ships_the_whole_template_root` and
`::test_an_installed_forge_generates_the_same_project_as_a_checkout` — the second
being the only test in the suite that exercises forge the way a user who ran
`pip install` does.

**Q3. Shape of the data passed to copier.** Three declared questions (`plugin`,
`service`, `domain`, plus `template_subdir` and `forge_version`) rather than one
question per business field.
→ **DECISION: the five-key shape.** Only the declared questions survive the
update; a single `domain` dict avoids duplicating the pydantic schema in
`copier.yml`, at the price of a more verbose `.copier-answers.yml` (readable,
versioned, and that is precisely what we want to re-read).

**Q4. Cross-domain checks.** Two options: rules written in the core (which would
then become domain-dependent), or projections declared by the plugins and
compared by the core.
→ **DECISION: `forge_projection` + generic comparison**, with
`forge_consistency` as the escape hatch. The core stays agnostic, and a third
plugin (Terraform…) inherits the checks without touching the core.

**Q5. Legacy spec converter.** No legacy `forge.yml` exists outside the original
repositories (5 ansible specs + 2 helm specs, all in `tests/`).
→ **DECISION: no `forge import` command shipped.** Confirmed: no legacy
`forge.yml` exists outside the original repositories. A test helper
(`tests/legacy_spec.py`) converts the 7 specs to feed the parity snapshots of
phases 3 and 4.

**Q6. Repository-level files** (`README.md`, `Makefile`, `.gitignore`,
`.gitattributes` at the root of the target). The helm legacy generates them from
its `project/` template; in a monorepo they belong to no domain.
→ **DECISION: the core writes a non-domain minimum** (`forge.yml`, a `README.md`
listing the domains, `.gitattributes`); the helm `Makefile` and the Ansible
`.gitignore` stay **in their domain subdirectory** (`helm/Makefile`), which keeps
every domain self-contained and deletable.

> **Consequences observed in phase 2** — these three files are the only ones
> forge writes without going through copier, which is an assumed exception to the
> "rendering always goes through copier" rule:
> - they are not tracked by `copier update`, so `forge update` does not refresh
>   them; it is `forge generate` that brings them up to date;
> - `forge diff` therefore compares them **explicitly** (`(root)` heading), so as
>   never to announce "up to date" about something it would not have looked at;
> - the target's `forge.yml` is the **hand-edited source of truth**: when the
>   specification read *is* the target's own, it is not rewritten, since
>   re-serialising it would destroy the team's comments;
> - `README.md` and `.gitattributes` obey the same rule as the domain files: no
>   overwriting of a modified file without `--force`;
> - the index lists the domains **of the specification**, never those of the last
>   `--only`: a `forge generate --only ansible` must not make `helm/` disappear
>   from the README of a project where the `helm:` section still exists.

**Q7. Validation under Windows.** Finding: neither ansible-core, nor
ansible-lint, nor helm, nor kubeconform are installed on the Windows side; helm
4.2.4 and kubeconform 0.8.0 are present in WSL Debian; ansible-lint is installed
nowhere.
→ **DECISION: core runner with a WSL fallback** (port of
`tests/ansible_tools.py`). **`pipx install ansible-core ansible-lint` in WSL
Debian is on me, at the start of phase 3** (task recorded in PLAN.md); the
GitHub CI (Linux) remains the authority.

**Q8. Managing the repository and the template versions.** `copier update`
compares git references: by default the **latest tag**. In development,
`--ref HEAD` includes the uncommitted templates (verified).
→ **DECISION: `--ref HEAD` by default** (the render follows the working tree,
and so do the golden tests), `vX.Y.Z` tags placed at each phase to offer stable
update points to the generated projects.

**Q9. Galaxy collection versions of the generated project** — *a question opened
after the fact, arbitrated on 2026-09-24.* `requirements.yml` named the
collections without any constraint whatsoever:
`ansible-galaxy collection install -r requirements.yml` installed whatever
Galaxy served that day. forge's CI took the breakage first —
`community.postgresql` 5.0.0 removed `postgresql_set`, and a three-week-old
commit went red — but the same exposure was delivered to every generated
project. "Same specification, same output" says nothing as long as the output
names dependencies without a version.
→ **DECISION: a floor *and* a major ceiling**, allowed once per collection in
`plugins/ansible/catalog/collections.py`.
- **Per collection, never per role.** Two roles that depend on the same
  collection must not be able to contradict each other; a `RoleDefinition`
  therefore names only a collection name. A role naming a collection absent from
  the table breaks the plugin import, not the user's project.
- **The ceiling, and not only the floor.** A floor documents what the templates
  need, but protects against nothing: the breakage always comes from a major
  published *after* generation. *(Alternative rejected: floor only, less upkeep
  for forge, but the incident reproduces itself as-is at the user's, which is
  precisely what we refuse to ship.)*
- **Assumed consequence: forge has to follow the majors.** Without a regular
  version bump, the generated projects grow old. The procedure is the one for the
  tools pinned in `.github/workflows/ci.yml`: raise the version validated in CI,
  raise `max_major`, fix the templates if the major removed something, ship the
  bump in its own commit. A range stays **widenable by the user at their own
  hand**: `requirements.yml` is a file of their project, and the generated header
  says so.
- **The floor is never guessed.** When we know what the templates require, it
  says so (`community.postgresql >= 3.13.0` for `postgresql_alter_system`).
  Otherwise it is the version validated in CI, with the reason written in the
  generated file: forge does not claim to know what it has not tested, and the
  floor comes down the day someone verifies it.

> **Still exposed, outside this decision** — this decision bears only on the
> **collections** named by `requirements.yml`. Two tool installations remain
> without a version in what forge generates: `pip install --upgrade
> ansible-core ansible-lint` in the `.github/workflows/ansible-lint.yml` workflow
> of the Ansible project, and the `plugins/pipeline/tools.py` table, where
> `ansible-core`, `ansible-lint` **and the three collections** are still free and
> where the collection list is copied over. The first pins in three lines; the
> second requires that `pipeline` learn the `ansible` domain's versions without
> importing it — hence a projection, hence a separate decision.

**Q10. forge's own renderer versions** — *a question opened after the fact,
arbitrated on 2026-10-08.* Q9 pinned what the **generated** projects install.
What **forge itself** installs was still free: every entry in `pyproject.toml`
was a floor (`copier>=9.7`, `pydantic>=2.6`, …) with no lockfile anywhere, so
each CI run resolved whatever PyPI served that day — and `uv`, which did the
resolving, was unpinned too (fixed separately, in the commit that precedes this
entry). Two of those floors are not ordinary dependencies: **`copier` and
`jinja2` are the renderer.** They are the one dependency class that can change
generated output with no line of this repository having moved, which is exactly
what CLAUDE.md's *"same spec ⇒ same generated output"*, the golden trees and the
structural fingerprints exist to guarantee. A fingerprint that moves because a
transitive renderer bump landed overnight is a false alarm, and false alarms are
how a signal stops being read. Worse, `jinja2` was not even a declared
dependency: it arrives through `copier` (`jinja2>=3.1.6`), so it floated at two
removes.
→ **DECISION: a lockfile, used by CI; and no ceilings in the published
metadata.** `uv.lock` is committed, `ci.yml` installs with
`uv sync --locked --extra dev`, and the constraints in `pyproject.toml` stay
floors.

- **A lockfile, and not upper bounds.** Bounds were the tempting answer, because
  they look like Q9's *"the ceiling, and not only the floor"*. The analogy
  breaks on who owns the file. Q9's ceiling is written into `requirements.yml`,
  a file **of the user's project**, and the generated header tells them they may
  widen it by hand. `pyproject.toml` is forge's **published** metadata: a
  ceiling there is imposed on everyone who runs `pip install iac-forge`, is
  resolved against *their* dependency set, and cannot be widened by hand at all.
  `copier<10` would make forge the package that blocks someone else's upgrade,
  months after we stopped looking. The same decision, read correctly, lands on
  opposite answers for a generated file and for a published one.
  *(And bounding `jinja2` would have meant declaring a direct dependency on a
  library forge never imports — with the standing risk of pinning a version
  `copier` itself refuses.)*
- **Assumed consequence: forge tests one version and supports a range.** That
  asymmetry is deliberate, and it is worth saying out loud rather than leaving
  it implied: the golden trees and the fingerprints prove determinism **for the
  locked renderer**, not for every version the floors admit. Nothing here checks
  that `copier` 9.7 — the declared floor — still renders these templates. The
  floor states what we believe, the lockfile states what we verified, and they
  are not the same claim.
- **The lockfile needs a bump path, or it is Q9's problem upside down.** A
  pinned renderer that never updates ages exactly the way a pinned action does.
  `.github/dependabot.yml` therefore watches the `uv` ecosystem — which also
  retires the reason that file used to give for watching only `github-actions`.
  A renderer bump then arrives as a reviewable PR, *which may legitimately move
  the fingerprints*; that movement is read and explained, never re-baselined on
  sight (DECISIONS.md, the note at the top). That watcher runs
  `versioning-strategy: lockfile-only`, because its default would rewrite the
  very floors this decision keeps permissive — and the price of that setting is
  that it is weak on transitive packages, `jinja2` among them. The watcher is
  therefore a partial bump path, and `uv lock --upgrade` run by hand is the
  complete one. Written down in `dependabot.yml`, beside the setting.
- **Local development syncs from the lockfile too.** `CONTRIBUTING.md` and the
  README now say `uv sync`, not `uv pip install -e ".[dev]"`. Otherwise a
  contributor reproducing a CI failure is not reproducing CI's renderer, which
  is the one difference that would matter.
- **Rejected: accept the drift and write down why.** Defensible for a resolver.
  Not for the renderer, in a repository whose central promise is that the same
  specification yields the same bytes.

**Q11. Actions in *generated* workflows — pinned, and the bump path explained
rather than installed.** Opened by ZED-31 on 2026-10-08, after ZED-30 pinned
every `uses:` in forge's own `.github/workflows/`. The workflows forge *emits*
still carried floating tags: `actions/checkout@v4` in the `pipeline` and
`ansible` templates, `actions/setup-python@v5` in `ansible`.

The blast radius is not ZED-30's, and that is the whole question. A moved tag in
our `release.yml` puts a bad wheel on PyPI under our name — bad, and ours to
notice. A moved tag in generated output runs in **our users' repositories**, with
permissions we cannot see, and we never find out. Against that: a SHA pinned into
a *template* goes stale the moment it is rendered, and the generated project has
no Dependabot to move it. Copying ZED-30's answer across unchanged reproduces the
failure that `dependabot.yml` was added to prevent.

**Decision: pin the SHA, and explain the bump path in the generated file's own
header. Do not generate `.github/dependabot.yml`.**

- `actions/checkout` is pinned at `11d5960a…` (v4.4.0), `actions/setup-python` at
  `a26af69b…` (v5.6.0), each with the release in a trailing comment — the same
  shape ZED-30 used on our side.
- **The major each template already declared is kept.** v4 for `checkout`, v5 for
  `setup-python`, not the v7/v5 forge itself runs. This question is about pinning,
  not upgrading; moving a user's action across a major is a separate change with
  its own compatibility surface, and smuggling it in here would be the kind of
  passenger commit `ci.yml`'s own header forbids.
- ZED-30's annotated-tag trap was **checked, not assumed**: both refs resolve with
  `object.type == commit`, so the ref SHA and the peeled commit are the same value
  here. The check is the habit, not the result.
- **Rejected: also generate `dependabot.yml`** (complete, and consistent with what
  we do to ourselves). It imposes a weekly PR stream on every generated repository
  whether the user wanted a bot or not, and forge's remit is to scaffold a project,
  not to enrol it in automation. Still the right answer the moment anyone asks —
  the header already names the file, so adopting it is one commit here and one
  file there.
- **Rejected: keep floating tags and document the trade-off.** Defensible for a
  scaffold, since the user owns the repository. But forge's README calls its output
  production-grade, and a supply-chain weakness shipped inside that claim is worse
  than shipping no workflow at all.

The cost of this choice is honest and worth stating: a generated pin ages, and
nothing in the generated repository moves it. The header is the whole mitigation,
which is a bet on the reader — the same bet every commented line in forge's output
already makes.
