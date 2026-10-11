# Tree of the forge repository

Moved out of `DESIGN.md` §9 by ZED-226, for the reason given in
`docs/ARBITRATIONS.md`: `DESIGN.md` was over the cap and this is a record of
what the repository turned out to be, not a part of the design anyone reads
forward. `DESIGN.md` §9 points here. Recorded as D18 in `DECISIONS.md`.

This file is named in `TRACKED_PROSE` in `scripts/check_file_sizes.py`, so it
caps itself at the same thresholds as the other registers.

---

*Observed after phase 10, and no longer planned.*

```
forge/
├── CLAUDE.md  PLAN.md  MIGRATION.md  DESIGN.md  README.md  CHANGELOG.md
├── CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  LICENSE
├── copier.yml                     # single root template (§5.1); copied into the
├── partials/header.jinja          # wheel under forge/ so an install can render (§8 Q2-bis)
├── pyproject.toml                 # uv, python >=3.11
├── .gitattributes                 # * text=auto eol=lf
├── examples/                      # six specifications, all tested
├── src/forge/
│   ├── cli.py  errors.py  jinja_ext.py  pipeline.py
│   ├── spec/         io.py  service.py  assembly.py  names.py  types.py
│   ├── plugins_api/  hookspecs.py  manager.py  types.py  checks.py
│   ├── interview/    prompter.py  service_flow.py
│   ├── render/       copier_runner.py  scaffold.py  diff.py
│   ├── validate/     runner.py  tools.py  wsl.py  consistency.py
│   └── plugins/
│       ├── demo/        plugin.py  template/        # core tests only
│       ├── ansible/     plugin.py  spec.py  catalog/  interview.py  validators.py  template/
│       ├── helm/        plugin.py  spec.py  catalog/  interview.py  validators.py  template/
│       ├── terraform/   plugin.py  spec.py  catalog/  interview.py  validators.py  template/  hcl.py
│       ├── monitoring/  plugin.py  spec.py  catalog/  interview.py  validators.py  template/  render.py
│       └── pipeline/    plugin.py  spec.py  jobs.py  tools.py  interview.py  validators.py  template/
└── tests/
    ├── specs/  golden/
    ├── conftest.py  scripted_prompter.py  isolated_domain.py  fake_domains/
    └── test_*.py
```

### Divergences from what this document planned

| Addition | Why |
| --- | --- |
| `pipeline.py` | so that `cli.py` carries no logic: the operations are callable without a terminal |
| `interview/service_flow.py`, `render/scaffold.py`, `render/diff.py` | single responsibility, and the 600-line limit |
| `plugins_api/checks.py` | four domains were rewriting the same "unknown environment" check; it only speaks of `service.environments`, so it stays agnostic |
| `plugins/terraform/hcl.py` | `terraform fmt` aligns the `=` of consecutive lines: a template cannot align keys whose length it does not know, the projection can |
| `plugins/monitoring/render.py` | an alert annotation and the annotation expected by its unit test are computed together, otherwise they diverge |
| `plugins/pipeline/jobs.py`, `tools.py` | deriving jobs from a `GenerationContext`, and knowing how to install the tools the commands name — the only table in the project that names binaries |
| `partials/` at the root | macros shared between templates, resolved by copier's Jinja loader. Copied into the package for the wheel (§8 Q2-bis) |

`tests/parity/` existed throughout the port then was removed in phase 10, along
with `_legacy/` (see `MIGRATION.md`, closing section).

600-line-per-file limit (global CLAUDE.md): the largest file in `src/` has 420;
the largest test module, 468.
