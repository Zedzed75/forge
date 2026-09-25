"""Interview for the Helm domain.

The core has already asked for the service identity and its environments; this
interview asks none of that again. It describes what is specific to Helm: the
targeted Kubernetes version, the image, and the chart components with their
resources.

The questionnaire follows the structure of the catalog (`catalog/families.py`):
for each component we ask for its workload kind, then the resource families to
attach to it. The user never has to know the name of a Kubernetes kind — the
catalog translates it.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter, Validator
from forge.plugins.helm.catalog.registry import get_family
from forge.plugins.helm.constants import KUBERNETES_VERSIONS
from forge.plugins.helm.enums import (
    AddonKind,
    ComponentKind,
    ImagePullPolicy,
    NamespaceStrategy,
    TagStrategy,
)
from forge.spec.names import DNS_LABEL_RE
from forge.spec.service import ServiceSpec

#: Addons offered for selection, in catalog order.
OFFERED_ADDONS: tuple[str, ...] = (
    AddonKind.SERVICE.value,
    AddonKind.INGRESS.value,
    AddonKind.CONFIGMAP.value,
    AddonKind.SECRET.value,
    AddonKind.HPA.value,
    AddonKind.PDB.value,
    AddonKind.SERVICEACCOUNT.value,
    AddonKind.NETWORKPOLICY.value,
)

#: Addons ticked by default: the bare minimum of an exposable service.
DEFAULT_ADDONS: tuple[str, ...] = (AddonKind.SERVICE.value,)


def _dns_label(value: str) -> str | None:
    if not DNS_LABEL_RE.match(value.strip()):
        return "expected a DNS label: lowercase letters, digits and inner hyphens"
    return None


def _positive_int(value: str) -> str | None:
    text = value.strip()
    if not text.isdigit() or int(text) < 1:
        return "expected a positive integer"
    return None


def _non_empty(value: str) -> str | None:
    return None if value.strip() else "value required"


def _family_label(name: str) -> str:
    """Label of an addon: its catalog summary, not its kind."""
    family = get_family(name)
    return f"{family.summary} ({family.kind})"


def _ask_component(prompter: Prompter, index: int, first: bool) -> dict[str, Any] | None:
    """Question a component; return None when the user stops."""
    prompt = "Component name" if first else f"Name of component #{index} (empty to finish)"
    validator: Validator | None = _dns_label if first else None
    name = prompter.text(prompt, default="api" if first else "").strip()
    if not name:
        return None
    if validator is None and _dns_label(name) is not None:
        prompter.note(f"Name ignored: {_dns_label(name)}")
        return None

    kind = prompter.select(
        f"Workload kind for '{name}'",
        choices=[
            (ComponentKind.DEPLOYMENT.value, "Stateless, replicable (Deployment)"),
            (ComponentKind.STATEFULSET.value, "Stateful, one volume per pod (StatefulSet)"),
            (ComponentKind.CRONJOB.value, "Scheduled task (CronJob)"),
        ],
        default=ComponentKind.DEPLOYMENT.value,
    )

    component: dict[str, Any] = {"name": name, "kind": kind}

    if kind == ComponentKind.CRONJOB.value:
        # A CronJob has no Service, no Ingress and no autoscaling: do not offer them.
        component["cron"] = {
            "schedule": prompter.text(
                f"Schedule of '{name}' (five-field cron)", default="0 3 * * *"
            ).strip()
        }
        return component

    available = [addon_name for addon_name in OFFERED_ADDONS]
    if kind == ComponentKind.STATEFULSET.value:
        # The headless Service and the persistence are imposed by the model.
        available = [a for a in available if a != AddonKind.SERVICE.value]

    addons = prompter.checkbox(
        f"Resources to attach to '{name}'",
        choices=[(a, _family_label(a)) for a in available],
        default=[a for a in DEFAULT_ADDONS if a in available],
    )
    if kind == ComponentKind.STATEFULSET.value:
        addons = [AddonKind.SERVICE.value, *addons]
    component["addons"] = addons

    port = prompter.text(
        f"Container listening port of '{name}'", default="8080", validate=_positive_int
    )
    component["container_port"] = int(port)

    if AddonKind.INGRESS.value in addons:
        component["ingress"] = {
            "base_domain": prompter.text(
                f"Base domain exposing '{name}'",
                default="example.net",
                validate=_non_empty,
            ).strip()
        }
    return component


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduct the Helm domain interview and return its forge.yml section.

    Returns None when the user declares no component: a chart without a
    component would have nothing to deploy.
    """
    prompter.note("── Helm chart ──")

    version = prompter.select(
        "Targeted Kubernetes version",
        choices=[(v, v) for v in KUBERNETES_VERSIONS],
        default=KUBERNETES_VERSIONS[-1],
    )
    chart_version = prompter.text("Chart version (semver)", default="0.1.0").strip()
    app_version = prompter.text(
        "Application version (appVersion)", default="1.0.0", validate=_non_empty
    ).strip()

    prompter.note("── Image ──")
    registry = prompter.text("Image registry", default="docker.io").strip()
    repository = prompter.text(
        "Image repository (without the registry)", default=service.name, validate=_non_empty
    ).strip()
    strategy = prompter.select(
        "How is the image tag chosen?",
        choices=[
            (TagStrategy.APP_VERSION.value, "The tag follows the chart appVersion"),
            (TagStrategy.PER_ENV.value, "One tag per environment"),
            (TagStrategy.FIXED.value, "One fixed tag, the same everywhere"),
        ],
        default=TagStrategy.APP_VERSION.value,
    )
    image: dict[str, Any] = {
        "registry": registry,
        "repository": repository,
        "strategy": strategy,
        "pull_policy": ImagePullPolicy.IF_NOT_PRESENT.value,
    }
    if strategy == TagStrategy.FIXED.value:
        image["tag"] = prompter.text("Fixed tag", default="1.0.0", validate=_non_empty).strip()

    prompter.note("── Namespaces ──")
    namespace_strategy = prompter.select(
        "How are the namespaces split?",
        choices=[
            (NamespaceStrategy.PER_ENV.value, "One namespace per environment"),
            (NamespaceStrategy.SINGLE.value, "A single, shared namespace"),
            (NamespaceStrategy.CUSTOM.value, "A namespace named for each environment"),
        ],
        default=NamespaceStrategy.PER_ENV.value,
    )

    prompter.note("── Chart components ──")
    components: list[dict[str, Any]] = []
    while True:
        component = _ask_component(prompter, len(components) + 1, not components)
        if component is None:
            break
        components.append(component)
        if not prompter.confirm("Add another component?", default=False):
            break
    if not components:
        return None

    section: dict[str, Any] = {
        "chart_version": chart_version,
        "app_version": app_version,
        "kubernetes": {"version": version},
        "namespace_strategy": namespace_strategy,
        "image": image,
        "components": components,
    }

    if namespace_strategy == NamespaceStrategy.CUSTOM.value:
        section["environments"] = {
            env.name: {
                "namespace": prompter.text(
                    f"Namespace of environment '{env.name}'",
                    default=f"{service.name}-{env.name}",
                    validate=_non_empty,
                ).strip()
            }
            for env in service.environments
        }

    section["extras"] = {
        "makefile": prompter.confirm("Generate a Makefile of shortcuts?", default=True),
        "helm_tests": prompter.confirm("Generate a `helm test`?", default=True),
    }
    return section
