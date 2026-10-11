"""The reference trees the fingerprint harness tests, and the files it edits.

Shared by `tests/test_fingerprint.py` (what the fingerprint does to a generated
tree) and `tests/test_fingerprint_rules.py` (the rules the reduction rests on),
split out of the single 713-line test module in ZED-223.

It sits outside pytest's `test_*` glob on purpose: a test module importing from
another test module makes collection order part of the contract, and the
imported one's fixtures leak into the importer. A plain module is just a module.

Nothing here asserts anything. It is the registry of *which* trees and *which
files inside them* the two modules talk about -- the one thing both need to
agree on, since a case name is also the name of a stored fingerprint.
"""

from __future__ import annotations

from tests.conftest import spec_files

#: One case per reference spec, as in the golden harness.
CASES = [path.stem for path in spec_files()]

#: Tree used by the sensitivity tests: the only reference case carrying both an
#: Ansible project (handlers and `notify:`) and a Helm chart (helpers).
MIXED_CASE = "two-domains"

#: Tree used by the GitHub Actions tests: the reference case whose repository
#: root is a workflow, with several jobs and a step label in each.
WORKFLOW_CASE = "pipeline-github"

#: Tree used by the HCL test: the reference case with Terraform variables, whose
#: `description` arguments are the one prose field normalised in a `text` file.
TERRAFORM_CASE = "terraform-full"

#: The workflow of `WORKFLOW_CASE`, which carries all three kinds of `name:`.
WORKFLOW = ".github/workflows/ci.yml"

#: Files of `MIXED_CASE` the sensitivity tests edit.
HANDLERS = "ansible/roles/postgresql/handlers/main.yml"
TASKS = "ansible/roles/postgresql/tasks/main.yml"
RULES = "ansible/roles/firewall/tasks/ufw.yml"
GROUP_VARS = "ansible/group_vars/all.yml"
CHART_TEMPLATE = "helm/charts/storefront/templates/deployment-api.yaml"
