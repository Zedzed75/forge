# Project: helm-forge
Deterministic generator of complete, fully commented Kubernetes/Helm projects.

## Core principle
- Generation is done 100% through Jinja2 templates rendered from a specification (ProjectSpec).
- No calls to any LLM or external API, now or as a future option.
- Same spec => same output, byte for byte. This is a requirement, not a preference.

## Conventions
- Python 3.11+, minimal dependencies: typer, questionary, jinja2, pyyaml, pydantic.
- Jinja2 and Helm/Go templating both use `{{ }}`: use custom Jinja2 delimiters
  (e.g. `[[ ]]`) in the generator so Helm template syntax passes through untouched.
- All generated files are commented: a header in every file explaining its purpose,
  a comment above every block in values.yaml (what it does, allowed values, defaults),
  and comments in templates explaining non-obvious logic.
- Standard Helm chart layout: Chart.yaml, values.yaml, values-<env>.yaml,
  templates/, templates/_helpers.tpl, templates/NOTES.txt, templates/tests/, README.md.
- Follow Helm best practices: standard labels (app.kubernetes.io/*), helpers for names
  and labels, no hardcoded values in templates, resources/probes/securityContext always
  exposed in values.
- Every generated chart must pass `helm lint`, render cleanly with `helm template` for every
  environment, and validate with `kubeconform` (strict mode) against the target Kubernetes version.
- Comments and documentation in French; resource names, values keys and file names in English.
- Run the test suite after every significant change.
- Commit at the end of every completed phase with a clear message.
