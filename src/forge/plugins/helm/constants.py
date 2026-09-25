"""Helm domain constants: targeted versions, apiVersions, length caps.

Port of `helm_forge.constants` (MIGRATION.md §4), stripped of what belongs to
the core: the regular expressions moved to `names.py`, and `SPEC_FILENAME` /
`SPEC_SCHEMA_VERSION` are replaced by the root model's `forge_version`
(`forge.spec.assembly`).

This module holds immutable data only and depends on no other module: it is the
base of the plugin's import stack.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Kubernetes
# --------------------------------------------------------------------------

#: Window of supported Kubernetes versions (N-2 to N). The last entry is the
#: most recent one and serves as the default. Arbitration H12: this window is
#: authoritative; the `1.31` example of DESIGN.md §3 is what gets corrected, not
#: the window. It is revalidated against the `kubeconform` actually installed,
#: never widened to make an example pass.
KUBERNETES_VERSIONS: Final[tuple[str, ...]] = ("1.34", "1.35", "1.36")

#: Version offered by default: the latest stable one of the window.
DEFAULT_KUBERNETES_VERSION: Final[str] = KUBERNETES_VERSIONS[-1]

#: apiVersion used per resource family. Every generated resource is stable over
#: the supported window; this table exists to absorb a future version divergence
#: painlessly.
API_VERSIONS: Final[dict[str, str]] = {
    "workload": "apps/v1",
    "batch": "batch/v1",
    "hpa": "autoscaling/v2",
    "pdb": "policy/v1",
    "ingress": "networking.k8s.io/v1",
    "networkpolicy": "networking.k8s.io/v1",
    "rbac": "rbac.authorization.k8s.io/v1",
}

# --------------------------------------------------------------------------
# Length caps
# --------------------------------------------------------------------------
#
# Kubernetes limits a DNS-1123 label to 63 characters. The generator suffixes
# resources (`-headless`, `-serviceaccount`), hence a comfortable margin on the
# service name and on the component names.
#
# Arbitration H6: the caps that bear on the shared `service:` block
# (`MAX_SERVICE_NAME_LENGTH`, `MAX_DESCRIPTION_LENGTH`,
# `MAX_ENVIRONMENT_NAME_LENGTH`) are checked by the **plugin cross-check**, never
# by the core: they are constraints of `Chart.yaml` and of the 63-character
# budget of Kubernetes resource names, and the core has no business knowing
# Helm. Only `MAX_COMPONENT_NAME_LENGTH` is enforced by the model, because the
# components live in the `helm:` section.

#: Cap on the service name (`service.name`), used as the chart name.
MAX_SERVICE_NAME_LENGTH: Final[int] = 40

#: Cap on a component name (`helm.components[].name`).
MAX_COMPONENT_NAME_LENGTH: Final[int] = 20

#: Cap on an environment name (`service.environments[].name`).
MAX_ENVIRONMENT_NAME_LENGTH: Final[int] = 20

#: Cap on the description (`service.description`), echoed in `Chart.yaml`.
MAX_DESCRIPTION_LENGTH: Final[int] = 200

# --------------------------------------------------------------------------
# Fallback values for the shared block
# --------------------------------------------------------------------------
#
# `service.owner` and `service.owner_email` feed the `maintainers` list of
# `Chart.yaml`, which does not accept an empty value. `owner_email` being
# optional in the core, the plugin must know what to write in its absence.

#: Maintainer written into `Chart.yaml` when `service.owner` is empty.
DEFAULT_MAINTAINER_NAME: Final[str] = "unknown"

#: Address written into `Chart.yaml` when `service.owner_email` is absent.
DEFAULT_MAINTAINER_EMAIL: Final[str] = "unknown@example.com"
