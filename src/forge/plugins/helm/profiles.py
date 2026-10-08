"""Resource profiles and per-environment profiles.

Port of `helm_forge.models.profiles` (MIGRATION.md §4). This module holds data
and pure functions only, with no dependency on pydantic: it is importable from
any model without risking an import cycle, and `derive.py` uses it to compute the
implicit values.

**Why recognition by name survives** (arbitration H2): it is what makes a minimal
`forge.yml` equivalent to a complete one — an environment named `prod` gets three
replicas, an HPA and a host without infix, without the user having to write
anything. MIGRATION.md §4 explicitly asks that it be kept. The core's explicit
`service.environments[].production` flag **overrides** it when present: see
:func:`profile_for`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from forge.plugins.helm.names import QUANTITY_RE

# --------------------------------------------------------------------------
# Resource profiles
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceValues:
    """Four Kubernetes quantities describing a container's requests and limits."""

    cpu_request: str
    memory_request: str
    cpu_limit: str
    memory_limit: str


#: Templates offered by the questionnaire. Deliberately modest: a generated
#: chart must be able to start on a development cluster without exhausting the
#: quota. The `custom` profile is absent: it fills nothing in.
RESOURCE_PROFILES: Final[dict[str, ResourceValues]] = {
    "small": ResourceValues("50m", "64Mi", "200m", "128Mi"),
    "medium": ResourceValues("250m", "256Mi", "1", "512Mi"),
    "large": ResourceValues("1", "1Gi", "2", "2Gi"),
}


# --------------------------------------------------------------------------
# Per-environment profiles
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvironmentProfile:
    """Values derived automatically for a given environment.

    These values are never asked of the user: they feed `values-<env>.yaml`
    directly, where they stay editable by hand.
    """

    #: Replica count of the workloads (Deployment, StatefulSet).
    replicas: int

    #: Horizontal autoscaling on for the components carrying the `hpa` addon.
    hpa_enabled: bool

    #: Disruption budget on for the components carrying the `pdb` addon.
    pdb_enabled: bool

    #: Log level written into the component configuration.
    log_level: str

    #: Multiplier applied to the requests/limits of the resource profile.
    resource_multiplier: int

    #: When true, the Ingress host includes the environment name: production
    #: exposes `<service>.<domain>`, the others `<service>.<env>.<domain>`.
    host_includes_env: bool


#: Profiles recognised by their name. An environment with an unexpected name gets
#: `DEFAULT_ENVIRONMENT_PROFILE`, that is to say the most cautious behaviour.
ENVIRONMENT_PROFILES: Final[dict[str, EnvironmentProfile]] = {
    "dev": EnvironmentProfile(
        replicas=1,
        hpa_enabled=False,
        pdb_enabled=False,
        log_level="debug",
        resource_multiplier=1,
        host_includes_env=True,
    ),
    "staging": EnvironmentProfile(
        replicas=2,
        hpa_enabled=False,
        pdb_enabled=True,
        log_level="info",
        resource_multiplier=1,
        host_includes_env=True,
    ),
    "prod": EnvironmentProfile(
        replicas=3,
        hpa_enabled=True,
        pdb_enabled=True,
        log_level="info",
        resource_multiplier=2,
        host_includes_env=False,
    ),
}

#: Profile applied to any environment outside the list above.
DEFAULT_ENVIRONMENT_PROFILE: Final[EnvironmentProfile] = EnvironmentProfile(
    replicas=1,
    hpa_enabled=False,
    pdb_enabled=False,
    log_level="info",
    resource_multiplier=1,
    host_includes_env=True,
)

#: Key of the production profile, the only target of the `production: true` flag.
PRODUCTION_PROFILE_KEY: Final[str] = "prod"

#: Common aliases, so that `production` behaves like `prod` and `stage` like
#: `staging`. The recognition is literal: it guesses nothing.
ENVIRONMENT_ALIASES: Final[dict[str, str]] = {
    "production": "prod",
    "prd": "prod",
    "stage": "staging",
    "stg": "staging",
    "develop": "dev",
    "development": "dev",
}


def profile_key(name: str) -> str:
    """Profile key matching `name`, aliases resolved."""
    return ENVIRONMENT_ALIASES.get(name, name)


def profile_for_environment(name: str) -> EnvironmentProfile:
    """Profile associated with an environment name, by recognition of the name.

    Ported identically from the legacy tool. `derive.py` must go through
    :func:`profile_for`, which takes the core's explicit flag into account.
    """
    return ENVIRONMENT_PROFILES.get(profile_key(name), DEFAULT_ENVIRONMENT_PROFILE)


def is_production_name(name: str) -> bool:
    """Tell whether `name` is recognised as a production environment.

    Serves the plugin cross-check: when this recognition and the
    `service.environments[].production` flag diverge, a *warning* level `Issue`
    is emitted rather than deciding silently (arbitration H2).
    """
    return profile_key(name) == PRODUCTION_PROFILE_KEY


def profile_for(name: str, *, production: bool = False) -> EnvironmentProfile:
    """Profile retained for an environment, arbitration H2 applied.

    `production=True` (that is, the core's `service.environments[].production`)
    forces the production profile, and therefore `host_includes_env=False`.
    Otherwise recognition by name applies: it is what makes a minimal spec
    equivalent to a complete one.
    """
    if production:
        return ENVIRONMENT_PROFILES[PRODUCTION_PROFILE_KEY]
    return profile_for_environment(name)


# --------------------------------------------------------------------------
# Arithmetic on Kubernetes quantities
# --------------------------------------------------------------------------

_QUANTITY_PARTS: Final[re.Pattern[str]] = re.compile(
    r"^([0-9]+(?:\.[0-9]+)?)([a-zA-Z]*)$"
)


def scale_quantity(quantity: str, factor: int) -> str:
    """Multiply a Kubernetes quantity by an integer, keeping its suffix.

    `scale_quantity("50m", 2)` returns `"100m"`, `scale_quantity("1", 2)`
    returns `"2"`. The result is rendered without a decimal part when it comes
    out even, which guarantees an identical rendering from one run to the next.
    """
    if factor == 1:
        return quantity
    match = _QUANTITY_PARTS.match(quantity)
    if match is None:  # pragma: no cover - guarded upstream by validation
        raise ValueError(f"invalid Kubernetes quantity: {quantity!r}")
    number, suffix = match.groups()
    scaled = float(number) * factor
    rendered = str(int(scaled)) if scaled.is_integer() else f"{scaled:g}"
    return f"{rendered}{suffix}"


def is_valid_quantity(quantity: str) -> bool:
    """Tell whether the string is an acceptable Kubernetes quantity."""
    return bool(QUANTITY_RE.match(quantity))
