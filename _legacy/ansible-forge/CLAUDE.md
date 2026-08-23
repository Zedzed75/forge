# Project: ansible-forge
Deterministic generator of complete, fully commented Ansible projects.

## Core principle
- Generation is done 100% through Jinja2 templates rendered from a specification (ProjectSpec).
- No calls to any LLM or external API, now or as a future option.
- Same spec => same output, byte for byte. This is a requirement, not a preference.

## Conventions
- Python 3.11+, minimal dependencies: typer, questionary, jinja2, pyyaml, pydantic.
- All generated Ansible code is commented: a header in every file explaining its purpose,
  an explicit `name:` on every task, and a comment on every variable in group_vars/host_vars
  (what it does and which values are allowed).
- Official Ansible layout: inventories/<env>/, roles/, playbooks/, group_vars/, host_vars/.
- Fully qualified module names only (ansible.builtin.*, community.*). Never invent a module.
- Every generated project must pass `ansible-lint` and `ansible-playbook --syntax-check`.
- Comments and documentation in French; variable names and file names in English.
- Run the test suite after every significant change.
- Commit at the end of every completed phase with a clear message.
