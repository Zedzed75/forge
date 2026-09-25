"""Values derived from the Helm specification, ready for the templates.

This module is the port of the **data computation** that
`helm_forge.models.spec` (inside its validators) and
`helm_forge.engine.renderer._base_context` performed before rendering anything.
Rendering and writing are copier's business now.

It covers the **static** part of the `domain` dict: chart identity, image,
components, slots per resource family. What varies per environment lives in
:mod:`forge.plugins.helm.derive_env`.

Absolute rule: **every output is JSON-serialisable and of frozen order**. Never a
pydantic object, never an `Enum` (`.value` everywhere), never a `set`: this dict
is written as-is into `.copier-answers.yml` and replayed by `copier update`.

Naming: the keys reuse those the legacy templates read on the pydantic objects,
so that converting a template comes down to prefixing `domain.` or to using the
loop variable of a `yield`. The three deliberate naming divergences are flagged
as comments where they appear.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.helm.constants import (
    DEFAULT_MAINTAINER_EMAIL,
    DEFAULT_MAINTAINER_NAME,
)
from forge.plugins.helm.enums import AddonKind
from forge.plugins.helm.jinja_ext import values_ref
from forge.plugins.helm.tree import (
    FAMILY_ORDER,
    component_families,
    test_connection_target,
)

# ---------------------------------------------------------------------------
# Chart identity
# ---------------------------------------------------------------------------


def maintainer(service: Any) -> dict[str, str]:
    """Maintainer written into `Chart.yaml`, never empty.

    `Chart.yaml` refuses a `maintainers` entry without a name nor an address,
    whereas `service.owner_email` is optional in the core: the plugin therefore
    supplies the fallbacks, which are those of the legacy `AppMeta` (`unknown`,
    `unknown@example.com`). The keys keep the legacy names `maintainer_name` and
    `maintainer_email`.
    """
    return {
        "maintainer_name": service.owner or DEFAULT_MAINTAINER_NAME,
        "maintainer_email": service.owner_email or DEFAULT_MAINTAINER_EMAIL,
    }


def kubernetes(helm: Any) -> dict[str, str]:
    """Targeted Kubernetes version, with its two derived forms.

    `kube_version_constraint` feeds `Chart.yaml`, `full_version` feeds
    `kubeconform`. Both were properties of the legacy model; a JSON-serialisable
    dict cannot carry a property, so they are materialised here.
    """
    return {
        "version": helm.kubernetes.version,
        "kube_version_constraint": helm.kubernetes.kube_version_constraint,
        "full_version": helm.kubernetes.full_version,
    }


def image(helm: Any) -> dict[str, Any]:
    """Default container image of the project.

    `strategy` and `pull_policy` are rendered as strings: the legacy templates
    already wrote `spec.image.strategy.value`.
    """
    return {
        "registry": helm.image.registry,
        "repository": helm.image.repository,
        "strategy": helm.image.strategy.value,
        "tag": helm.image.tag,
        "pull_policy": helm.image.pull_policy.value,
        "pull_secret_name": helm.image.pull_secret_name,
    }


def secrets(helm: Any) -> dict[str, str]:
    """How the secrets are managed. No secret value ever passes through here."""
    return {
        "strategy": helm.secrets.strategy.value,
        "store_name": helm.secrets.store_name,
        "refresh_interval": helm.secrets.refresh_interval,
    }


def extras(helm: Any) -> dict[str, bool]:
    """Extra files requested (`helmfile` and `ci` not ported: H7, H8)."""
    return {
        "makefile": helm.extras.makefile,
        "helm_tests": helm.extras.helm_tests,
    }


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


def addon_flags(component: Any) -> dict[str, bool]:
    """One boolean per addon, **every key always present**.

    Replaces the legacy templates' `component.has(AddonKind.SERVICE)` with
    `c.has.service`: a complete dict guarantees that a template cannot reference
    a missing key, even for an addon no component uses.
    """
    present = {addon.value for addon in component.addons}
    return {addon.value: addon.value in present for addon in AddonKind}


def probes(component: Any) -> dict[str, Any]:
    """Health probes. The port queried is `port_name`, never a number."""
    p = component.probes
    return {
        "enabled": p.enabled,
        "liveness_path": p.liveness_path,
        "readiness_path": p.readiness_path,
        "startup_enabled": p.startup_enabled,
        "initial_delay_seconds": p.initial_delay_seconds,
        "period_seconds": p.period_seconds,
        "timeout_seconds": p.timeout_seconds,
        "failure_threshold": p.failure_threshold,
    }


def resources(spec_resources: Any) -> dict[str, str]:
    """Requests and limits of a container, profile included (informative)."""
    return {
        "profile": spec_resources.profile.value,
        "cpu_request": spec_resources.cpu_request,
        "memory_request": spec_resources.memory_request,
        "cpu_limit": spec_resources.cpu_limit,
        "memory_limit": spec_resources.memory_limit,
    }


def security(component: Any) -> dict[str, Any]:
    """Security context of the pod and of the container."""
    s = component.security
    return {
        "strict": s.strict,
        "run_as_non_root": s.run_as_non_root,
        "run_as_user": s.run_as_user,
        "run_as_group": s.run_as_group,
        "fs_group": s.fs_group,
        "read_only_root_filesystem": s.read_only_root_filesystem,
        "allow_privilege_escalation": s.allow_privilege_escalation,
        "drop_capabilities": list(s.drop_capabilities),
        "seccomp_profile": s.seccomp_profile,
    }


def component_service(component: Any) -> dict[str, Any]:
    """Service exposing the workload."""
    s = component.service
    return {
        "type": s.type.value,
        "port": s.port,
        "headless": s.headless,
        "node_port": s.node_port,
        "annotations": dict(s.annotations),
    }


def ingress(component: Any) -> dict[str, Any]:
    """HTTP exposure. `class_name` is resolved here, never in a template.

    The model documents `class_name` as "absent = derived from the controller":
    the derivation is literal (`nginx` -> `nginx`, `traefik` -> `traefik`), but it
    has to exist somewhere, and a template has no business carrying it. The host,
    on the other hand, depends on the environment: it lives in
    `domain.environments`.
    """
    i = component.ingress
    return {
        "controller": i.controller.value,
        "base_domain": i.base_domain,
        "path": i.path,
        "path_type": i.path_type,
        "tls": i.tls,
        "issuer": i.issuer,
        "class_name": i.class_name or i.controller.value,
        "annotations": dict(i.annotations),
    }


def persistence(component: Any) -> dict[str, Any]:
    """Persistent volume attached to the workload."""
    p = component.persistence
    return {
        "enabled": p.enabled,
        "storage_class": p.storage_class,
        "size": p.size,
        "access_mode": p.access_mode.value,
        "mount_path": p.mount_path,
    }


def hpa(component: Any) -> dict[str, Any]:
    """Bounds and targets of the horizontal autoscaling."""
    h = component.hpa
    return {
        "min_replicas": h.min_replicas,
        "max_replicas": h.max_replicas,
        "target_cpu": h.target_cpu,
        "target_memory": h.target_memory,
    }


def networkpolicy(component: Any) -> dict[str, Any]:
    """Restriction of the ingress and egress network traffic."""
    n = component.networkpolicy
    return {
        "allow_from_same_namespace": n.allow_from_same_namespace,
        "allow_from_namespaces": list(n.allow_from_namespaces),
        "allow_dns": n.allow_dns,
        "allow_egress_all": n.allow_egress_all,
    }


def cron(component: Any) -> dict[str, Any] | None:
    """CronJob parameters, or `None` for any other type of component."""
    c = component.cron
    if c is None:
        return None
    return {
        "schedule": c.schedule,
        "concurrency_policy": c.concurrency_policy,
        "restart_policy": c.restart_policy,
        "successful_jobs_history_limit": c.successful_jobs_history_limit,
        "failed_jobs_history_limit": c.failed_jobs_history_limit,
        "backoff_limit": c.backoff_limit,
        "starting_deadline_seconds": c.starting_deadline_seconds,
    }


def component_context(component: Any, helm: Any, *, service_name: str) -> dict[str, Any]:
    """Complete context of a component, as every template sees it.

    Three values are **resolved** rather than copied, because every legacy
    template redid the same resolution:

    * `image_repository`: `component.image_repository or spec.image.repository`
      — never null, unlike the model field;
    * `values_ref`: the expression accessing the component's values key, which
      handles the hyphenated-name case (`[% set v = values_ref(component.name) %]`
      at the top of every legacy template);
    * `helper`: the prefix of the component helpers
      (`[% set h = spec.app.name ~ "." ~ component.name %]`).

    `families` lists the files this component will have generated: that is what
    lets the chart README document itself without reimplementing the filtering.
    """
    return {
        "name": component.name,
        "kind": component.kind.value,
        "is_workload": component.is_workload,
        "addons": [addon.value for addon in component.addons],
        "has": addon_flags(component),
        "families": component_families(component),
        "values_ref": values_ref(component.name),
        "helper": f"{service_name}.{component.name}",
        "image_repository": component.image_repository or helm.image.repository,
        "command": list(component.command),
        "args": list(component.args),
        "replicas": component.replicas,
        "container_port": component.container_port,
        "port_name": component.port_name,
        "probes": probes(component),
        "resources": resources(component.resources),
        "security": security(component),
        "service": component_service(component),
        "ingress": ingress(component),
        "persistence": persistence(component),
        "hpa": hpa(component),
        "pdb": {"min_available": component.pdb.min_available},
        "networkpolicy": networkpolicy(component),
        "rbac": {
            "create": component.rbac.create,
            "rules": [dict(rule) for rule in component.rbac.rules],
        },
        "config": {
            "keys": list(component.config.keys),
            "mount_as": component.config.mount_as,
        },
        "secret": {
            "keys": list(component.secret.keys),
            "mount_as": component.secret.mount_as,
        },
        "cron": cron(component),
    }


def components(helm: Any, *, service_name: str) -> list[dict[str, Any]]:
    """Component contexts, in the **order of the specification**.

    That order is significant on two counts: it fixes the order of the generated
    files, and the first exposed component carries the bare Ingress host.
    """
    return [
        component_context(component, helm, service_name=service_name)
        for component in helm.components
    ]


def component_slots(
    helm: Any, contexts: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """One slot per resource family, already filtered by kind and addon.

    On the model of `ansible.derive.role_slots`. Each key carries the list of the
    component contexts concerned, in the order of the specification; a template
    is then written, inside a **path name**, as:

        templates/[% yield c from domain.component_slots.ingress %]
        ingress-[[ c.name ]][% endyield %].yaml.jinja

    An empty list makes the file disappear. **Every key is always present**,
    including the empty ones, so that a template can never reference a missing
    key.

    `test_connection` is a case apart: zero or one element, the first exposed
    non-headless component, and only when `extras.helm_tests` (port of
    `planner.first_exposed` and of the condition on its call site).
    """
    slots: dict[str, list[dict[str, Any]]] = {
        family: [
            context for context in contexts if family in context["families"]
        ]
        for family in FAMILY_ORDER
    }
    target = test_connection_target(helm)
    by_name = {context["name"]: context for context in contexts}
    slots["test_connection"] = [] if target is None else [by_name[target.name]]
    return slots
