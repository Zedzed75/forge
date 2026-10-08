"""Paths the Helm domain is going to write — the planner reduced to its paths.

`helm_forge.engine.planner.plan` built the ordered list of the project files
**and** their rendering context. copier takes over rendering and multiplicity
(`yield` tags, MIGRATION.md §2.1); this module keeps only the list of paths, which
two generated files need:

* the chart README, which documents its structure file by file;
* the project README, which displays a tree.

**No ASCII tree builder is provided, and that is an observation, not an
oversight**: the tree in the legacy project README is an *annotated and folded*
list (each line carries an end-of-line comment, and `templates/` is not expanded).
A mechanical rendering from the paths would not reproduce it; it therefore stays
written literally in the template, where only the loop over the environments is
dynamic. The Ansible port, on the other hand, displayed a complete tree: hence
`tree.build_tree` over there and its absence here.

This module is the **only** place in the Helm domain that duplicates the knowledge
of the template tree: if a template is added, removed or renamed, it has to be
reflected here, otherwise both READMEs lie. The parity test catches it, because it
compares those files byte for byte.
"""

from __future__ import annotations

from typing import Any, Final

from forge.plugins.helm.enums import AddonKind, ComponentKind

#: Canonical order of the resource families of a component. It fixes the order of
#: the files in `templates/`, that of the lines of the chart README, and that of
#: the keys of `domain.component_slots`.
#:
#: The workload comes first (it is what the other resources accompany), then the
#: addons in the canonical order of `AddonKind`, `rbac` slotting in right after
#: `serviceaccount`: a Role and a RoleBinding only make sense with a subject, and
#: that subject is the component ServiceAccount.
FAMILY_ORDER: Final[tuple[str, ...]] = (
    "deployment",
    "statefulset",
    "cronjob",
    "service",
    "ingress",
    "configmap",
    "secret",
    "hpa",
    "pdb",
    "serviceaccount",
    "rbac",
    "networkpolicy",
)

#: Families carried by the component **type**: at most one per component.
KIND_FAMILIES: Final[dict[str, str]] = {
    ComponentKind.DEPLOYMENT.value: "deployment",
    ComponentKind.STATEFULSET.value: "statefulset",
    ComponentKind.CRONJOB.value: "cronjob",
}

#: Families carried by an **addon**, associated with the addon that triggers them.
#: `rbac` shares the `serviceaccount` addon: that is the only way to generate a
#: Role and a RoleBinding that have a subject.
ADDON_FAMILIES: Final[dict[str, str]] = {
    "service": AddonKind.SERVICE.value,
    "ingress": AddonKind.INGRESS.value,
    "configmap": AddonKind.CONFIGMAP.value,
    "secret": AddonKind.SECRET.value,
    "hpa": AddonKind.HPA.value,
    "pdb": AddonKind.PDB.value,
    "serviceaccount": AddonKind.SERVICEACCOUNT.value,
    "rbac": AddonKind.SERVICEACCOUNT.value,
    "networkpolicy": AddonKind.NETWORKPOLICY.value,
}

#: Label of each family, echoed as-is in the chart README: these are Kubernetes
#: `kind` names, written the way the API writes them.
FAMILY_LABELS: Final[dict[str, str]] = {
    "deployment": "Deployment",
    "statefulset": "StatefulSet",
    "cronjob": "CronJob",
    "service": "Service",
    "ingress": "Ingress",
    "configmap": "ConfigMap",
    "secret": "Secret",
    "hpa": "HorizontalPodAutoscaler",
    "pdb": "PodDisruptionBudget",
    "serviceaccount": "ServiceAccount",
    "rbac": "Role and RoleBinding",
    "networkpolicy": "NetworkPolicy",
    "test_connection": "Connection test",
}

#: Path, relative to the chart, of the test `helm test` runs. Unlike the other
#: resources it is never suffixed by the component name: there is only one per
#: chart (literal port of the legacy planner).
TEST_CONNECTION_PATH: Final[str] = "templates/tests/test-connection.yaml"

#: Files at the chart root, in the order of the legacy planner.
CHART_ROOT_FILES: Final[tuple[str, ...]] = ("Chart.yaml", "values.yaml")

#: Chart files written after the `values-<env>.yaml` ones.
CHART_TAIL_FILES: Final[tuple[str, ...]] = (".helmignore", "README.md")

#: Helm templates common to the whole chart.
CHART_SHARED_TEMPLATES: Final[tuple[str, ...]] = (
    "templates/_helpers.tpl",
    "templates/NOTES.txt",
)

#: Files written by copier but deliberately absent from the documentation:
#: `.copier-answers.yml` is generation plumbing, not part of the Helm project
#: (MIGRATION.md §7, divergence 1).
HIDDEN_ENTRIES: Final[tuple[str, ...]] = (".copier-answers.yml",)


def chart_dir(service_name: str) -> str:
    """Chart directory, relative to the domain root (`helm/`).

    Port of `planner.chart_dir`, where the root was that of the project: the
    output of each domain now lives in its own subdirectory (MIGRATION.md §7,
    divergence 2).
    """
    return f"charts/{service_name}"


def resource_filename(family: str, component_name: str) -> str:
    """File name of a resource, always suffixed by the component."""
    return f"{family}-{component_name}.yaml"


def component_families(component: Any) -> list[str]:
    """Resource families generated for a component, in canonical order.

    Filters by the component **type** (a single workload) then by its **addons**.
    This is the function `derive.component_slots` is the inverse of: it answers
    "which families for this component", the slot answers "which components for
    this family".
    """
    retained: list[str] = []
    for family in FAMILY_ORDER:
        expected = KIND_FAMILIES.get(family)
        if expected is not None:
            if component.kind.value == expected:
                retained.append(family)
            continue
        addon = ADDON_FAMILIES[family]
        if any(existing.value == addon for existing in component.addons):
            retained.append(family)
    return retained


def test_connection_target(helm: Any) -> Any | None:
    """First component reachable through a regular Service, when there is one.

    Literal port of `planner.first_exposed`, augmented with the condition the
    planner applied at its call site: without `extras.helm_tests`, no test is
    generated. A headless Service is ruled out — it has no virtual address, and a
    connection test based on the Service name would make no sense there.
    """
    if not helm.extras.helm_tests:
        return None
    for component in helm.components:
        if component.has(AddonKind.SERVICE) and not component.service.headless:
            return component
    return None


def chart_files(spec: Any) -> list[dict[str, str]]:
    """Generated Kubernetes resources, annotated, in file order.

    One entry per file of `templates/` specific to a component, plus the
    connection test when it is generated. The chart README makes it its "Chart
    structure" table; the sentence itself is composed in the template, this module
    only supplies the pieces (`label`, `component`).
    """
    helm = spec.helm
    entries: list[dict[str, str]] = []
    for component in helm.components:
        for family in component_families(component):
            entries.append(
                {
                    "family": family,
                    "label": FAMILY_LABELS[family],
                    "component": component.name,
                    "path": f"templates/{resource_filename(family, component.name)}",
                }
            )
    target = test_connection_target(helm)
    if target is not None:
        entries.append(
            {
                "family": "test_connection",
                "label": FAMILY_LABELS["test_connection"],
                "component": target.name,
                "path": TEST_CONNECTION_PATH,
            }
        )
    return entries


def expected_paths(spec: Any) -> list[str]:
    """Paths forge is going to write under `helm/`, in legacy planner order.

    The order is that of `planner.plan` — project-level files, chart root,
    per-environment values, shared templates, then the resources of each component
    — and not alphabetical order: it is the one the tables of the generated READMEs
    follow.

    Three divergences from the legacy tool, all recorded in MIGRATION.md §7: the
    `@spec` sentinel disappears (H10, divergence 3), the output lives under `helm/`
    (divergence 2), and `.copier-answers.yml` is added to it without being
    documented (divergence 1).
    """
    helm = spec.helm
    root = chart_dir(spec.service.name)

    paths: list[str] = ["README.md", ".gitignore"]
    if helm.extras.makefile:
        paths.append("Makefile")

    paths += [f"{root}/{name}" for name in CHART_ROOT_FILES]
    paths += [
        f"{root}/values-{env.name}.yaml" for env in spec.service.environments
    ]
    paths += [f"{root}/{name}" for name in CHART_TAIL_FILES]
    paths += [f"{root}/{name}" for name in CHART_SHARED_TEMPLATES]
    paths += [f"{root}/{entry['path']}" for entry in chart_files(spec)]
    return paths
