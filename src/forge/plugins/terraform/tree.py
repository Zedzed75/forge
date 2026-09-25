"""Paths the Terraform domain writes, and what each of them contains.

Same role -- and same warning -- as `plugins/ansible/tree.py` and
`plugins/helm/tree.py`: **this is the only place in the domain that duplicates
the knowledge of the template tree**. A template added, removed or renamed
without updating this module makes the generated READMEs wrong.

Arbitration R3 (PLAN.md) left this list to the plugin rather than inferring it
from a dry render, on one condition: that a test confronts it with the tree
really produced. It is `test_plugin_terraform.py` that holds it.

Every entry carries its description: the generated READMEs do not merely display
file names, they say what each of them is for.
"""

from __future__ import annotations

from typing import Any, Final, NamedTuple

from forge.plugins.terraform.catalog.registry import selected


class Entry(NamedTuple):
    """A generated file and the sentence that describes it."""

    #: Path relative to the root of the domain (`terraform/`).
    path: str

    #: What this file is for, in one sentence.
    purpose: str


#: Directory of the modules, relative to the root of the domain.
MODULES_DIR: Final[str] = "modules"

#: Directory of the environment roots.
ENVIRONMENTS_DIR: Final[str] = "environments"

#: Files of the module, apart from those of the retained families. The order is
#: the reading order: what Terraform requires, then what the module receives,
#: what it computes, what it returns.
MODULE_BASE: Final[tuple[Entry, ...]] = (
    Entry("versions.tf", "Terraform version and providers required by the module."),
    Entry("variables.tf", "Every input of the module, each one commented."),
    Entry("locals.tf", "Computed values: effective namespace, common labels."),
    Entry("outputs.tf", "What the module returns to its caller."),
    Entry("README.md", "Role of the module, inputs, outputs and traps of each family."),
)

#: Files of an environment root, in reading order.
ENVIRONMENT_FILES: Final[tuple[Entry, ...]] = (
    Entry("versions.tf", "Terraform version and providers required by this root."),
    Entry("backend.tf", "Where the state of this environment is kept."),
    Entry("providers.tf", "Configuration of the providers: targeted cluster, context."),
    Entry("variables.tf", "Inputs of the root, taken up from those of the module."),
    Entry("main.tf", "Call of the module, with the values of this environment."),
    Entry("outputs.tf", "Outputs brought up from the module."),
    Entry("terraform.tfvars", "Values of this environment. No secret value."),
)


def module_dir(service_name: str) -> str:
    """Path of the module, relative to the root of the domain."""
    return f"{MODULES_DIR}/{service_name}"


def environment_dir(environment: str) -> str:
    """Path of an environment root, relative to the root of the domain."""
    return f"{ENVIRONMENTS_DIR}/{environment}"


def family_file(family: str) -> str:
    """Name of the `.tf` file carrying a resource family."""
    return f"{family}.tf"


def module_files(spec: Any) -> list[dict[str, str]]:
    """Files of the module, base then retained families, in canonical order.

    Returned as dicts and not as `Entry`: the result goes into the `domain`
    dict, which has to stay JSON-serialisable (a `NamedTuple` would serialise as
    a list, and the templates would read `f[0]` instead of `f.path`).
    """
    entries = [
        {"path": entry.path, "purpose": entry.purpose} for entry in MODULE_BASE
    ]
    entries += [
        {
            "path": family_file(family.name),
            "purpose": f"{family.summary} ({', '.join(family.resources)}).",
        }
        for family in selected(spec.terraform.family_names())
    ]
    return entries


def environment_files() -> list[dict[str, str]]:
    """Files of an environment root, as JSON-serialisable dicts."""
    return [{"path": entry.path, "purpose": entry.purpose} for entry in ENVIRONMENT_FILES]


def root_files(spec: Any) -> list[dict[str, str]]:
    """Files at the `terraform/` level, apart from modules and environments."""
    entries = [
        {"path": "README.md", "purpose": "This file: how to use the project."},
        {
            "path": ".gitignore",
            "purpose": (
                "Excludes the state, the plans and the provider cache. The state "
                "carries values in plain text: it must never be committed."
            ),
        },
        {
            "path": ".copier-answers.yml",
            "purpose": "Answers of the template, read back by `forge update`. Do not edit.",
        },
    ]
    if spec.terraform.extras.tflint_config:
        entries.append(
            {
                "path": ".tflint.hcl",
                "purpose": "tflint rule set applied to the project.",
            }
        )
    if spec.terraform.extras.makefile:
        entries.append(
            {
                "path": "Makefile",
                "purpose": "Shortcuts: `make init ENV=prod`, `make plan ENV=prod`.",
            }
        )
    return sorted(entries, key=lambda entry: entry["path"])


def expected_paths(spec: Any) -> list[str]:
    """Every path written by the domain, sorted.

    This is the list the test confronts with the tree really rendered.
    """
    paths = [entry["path"] for entry in root_files(spec)]
    module = module_dir(spec.service.name)
    paths += [f"{module}/{entry['path']}" for entry in module_files(spec)]
    for env in spec.service.environments:
        root = environment_dir(env.name)
        paths += [f"{root}/{entry['path']}" for entry in environment_files()]
    return sorted(paths)


def resource_slots(spec: Any) -> dict[str, list[dict[str, str]]]:
    """File slots per family: `[{...}]` if retained, `[]` otherwise.

    Pattern shared with the two other domains (arbitration R4, DESIGN.md §5.3):
    a template specific to a family exists without a `[% if %]` having to appear
    in its path, and copier decides whether to write it through the `yield` tag.
    """
    retained = set(spec.terraform.family_names())
    from forge.plugins.terraform.catalog.registry import all_families

    return {
        family.name: (
            [{"name": family.name, "summary": family.summary}]
            if family.name in retained
            else []
        )
        for family in all_families()
    }
