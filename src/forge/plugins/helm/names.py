"""Naming rules specific to Helm and Kubernetes.

Port of `helm_forge.models.validators` and of the "regular expressions" part of
`helm_forge.constants` (MIGRATION.md §4).

`DnsLabel`, `Subdomain` and `SemVer` moved up into the core
(`forge.spec.types`), because they also serve the shared `service:` block. What
remains here describes what **Kubernetes and OCI** accept, not what forge
accepts: the core has no business knowing the grammar of an image repository nor
that of a resource quantity.
"""

from __future__ import annotations

import re
from typing import Annotated, Final

from pydantic import AfterValidator, Field

from forge.spec.names import check_pattern

# --------------------------------------------------------------------------
# Regular expressions
# --------------------------------------------------------------------------

#: Environment variable key, as expected in a ConfigMap or a Secret consumed
#: through `envFrom`.
ENV_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z_][A-Z0-9_]*$")

#: Kubernetes quantity: 100m, 1, 1.5, 512Mi, 10Gi...
QUANTITY_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]+(\.[0-9]+)?(m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$"
)

#: OCI image repository: lowercase, digits, separators, nested paths.
IMAGE_REPOSITORY_RE: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)*$"
)

#: Five-field cron schedule, as expected by a CronJob.
CRON_SCHEDULE_RE: Final[re.Pattern[str]] = re.compile(r"^(\S+\s+){4}\S+$")

#: Email address of the chart maintainer. The check is deliberately simple: it
#: refuses obviously wrong input without adding the `email-validator`
#: dependency. Used by the plugin cross-check, never by the core (arbitration
#: H6): it is a `Chart.yaml` constraint.
EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------------


def _env_key(value: str) -> str:
    """Validate an environment variable key (uppercase and underscores)."""
    return check_pattern(
        value,
        ENV_KEY_RE,
        "a valid key: uppercase letters, digits and underscores, not starting "
        "with a digit",
    )


def _quantity(value: str) -> str:
    """Validate a Kubernetes quantity (100m, 512Mi, 2, 10Gi...)."""
    return check_pattern(value, QUANTITY_RE, "a valid Kubernetes quantity")


def _image_repository(value: str) -> str:
    """Validate the path of an OCI image repository."""
    return check_pattern(value, IMAGE_REPOSITORY_RE, "a valid image repository")


def _http_path(value: str) -> str:
    """Validate an absolute HTTP path."""
    if not value.startswith("/"):
        raise ValueError(f"{value!r} must start with a slash")
    return value


def _absolute_path(value: str) -> str:
    """Validate an absolute mount path inside the container."""
    if not value.startswith("/"):
        raise ValueError(f"{value!r} must be an absolute path")
    return value


def _cron_schedule(value: str) -> str:
    """Validate a five-field cron schedule, surrounding spaces stripped."""
    return check_pattern(
        value.strip(),
        CRON_SCHEDULE_RE,
        'a five-field cron schedule (example: "0 3 * * *")',
    )


def is_valid_email(value: str) -> bool:
    """Tell whether `value` is an acceptable email address."""
    return bool(EMAIL_RE.match(value))


# --------------------------------------------------------------------------
# Exported annotated types
# --------------------------------------------------------------------------

#: ConfigMap or Secret key consumed through `envFrom` (UPPERCASE_WITH_UNDERSCORES).
EnvKey = Annotated[str, AfterValidator(_env_key)]

#: Kubernetes resource quantity (`50m`, `64Mi`, `1`, `10Gi`).
Quantity = Annotated[str, AfterValidator(_quantity)]

#: OCI image repository, without registry nor tag (`acme/shop`).
ImageRepository = Annotated[str, AfterValidator(_image_repository)]

#: Absolute HTTP path (`/healthz`).
HttpPath = Annotated[str, AfterValidator(_http_path)]

#: Absolute mount path inside the container (`/data`).
AbsolutePath = Annotated[str, AfterValidator(_absolute_path)]

#: Five-field cron schedule (`0 3 * * *`).
CronSchedule = Annotated[str, AfterValidator(_cron_schedule)]

#: Network port valid in the Kubernetes sense (1-65535).
Port = Annotated[int, Field(ge=1, le=65535)]

#: Integer percentage (1-100), used by the autoscaling targets.
Percentage = Annotated[int, Field(ge=1, le=100)]

#: Kubernetes port name (IANA_SVC_NAME format): at most 15 characters,
#: lowercase, digits and hyphens, at least one letter, no leading or trailing
#: hyphen, no two consecutive hyphens.
PORT_NAME_RE = re.compile(r"^(?!-)(?!.*--)(?=.*[a-z])[a-z0-9-]{1,15}(?<!-)$")


def _port_name(value: str) -> str:
    if not PORT_NAME_RE.match(value):
        raise ValueError(
            f"Invalid port name: '{value}'. Kubernetes imposes the "
            "IANA_SVC_NAME format: at most 15 characters, lowercase, digits and "
            "hyphens, at least one letter, no leading or trailing hyphen."
        )
    return value


#: Container port name, echoed by the Service and by the probes.
PortName = Annotated[str, AfterValidator(_port_name)]
