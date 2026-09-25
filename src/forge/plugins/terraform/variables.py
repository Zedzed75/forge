"""Input variables of the generated Terraform module.

A single declaration serves four files: the `variables.tf` of the module, the
`variables.tf` of each environment root, the module call in its `main.tf`, and
the `terraform.tfvars` of the environment. Redeclaring them in each template
would make them diverge on the first addition -- and Terraform does not report a
variable declared on the root side but never passed to the module: it is simply
without effect.

Absolute rule: **no secret value is ever written**. A `sensitive` variable has
no default value and does not appear in `terraform.tfvars`; it is provided
through `TF_VAR_<name>`, an environment variable of the CI or a vault.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Variable:
    """An input variable, as declared in `variables.tf`."""

    #: Name of the variable (HCL identifier).
    name: str

    #: HCL type: `string`, `number`, `bool`, `list(string)`, `map(string)`.
    type: str

    #: Description sentence, taken up as it is in `description`.
    description: str

    #: Default value, or `_ABSENT` if the variable is mandatory.
    default: Any = None

    #: True if the variable carries a default value (including `null`).
    has_default: bool = True

    #: Marks the value as secret: Terraform masks it in its outputs.
    sensitive: bool = False

    #: True if the value is passed through `terraform.tfvars` (therefore never
    #: secret, and computed per environment).
    per_environment: bool = False


def required(name: str, type_: str, description: str, *, sensitive: bool = False) -> Variable:
    """Variable with no default value: Terraform requires it to be provided."""
    return Variable(
        name=name,
        type=type_,
        description=description,
        default=None,
        has_default=False,
        sensitive=sensitive,
    )


def optional(
    name: str,
    type_: str,
    description: str,
    default: Any,
    *,
    per_environment: bool = False,
) -> Variable:
    """Variable with a default value, possibly overridden per environment."""
    return Variable(
        name=name,
        type=type_,
        description=description,
        default=default,
        has_default=True,
        per_environment=per_environment,
    )


#: Variables present whatever the retained families. They describe *what* the
#: module attaches itself to; the families add *what it sets up*.
COMMON_VARIABLES: tuple[Variable, ...] = (
    required(
        "service_name",
        "string",
        "Name of the service. Prefixes every created resource and feeds the "
        "app.kubernetes.io/name label.",
    ),
    required(
        "environment",
        "string",
        "Name of the environment (dev, staging, prod). Serves as a resource "
        "suffix and as the value of the app.kubernetes.io/instance label.",
    ),
    required(
        "namespace",
        "string",
        "Targeted Kubernetes namespace. Created by this module if the "
        "'namespace' family is retained, assumed to exist otherwise.",
    ),
    optional(
        "labels",
        "map(string)",
        "Labels applied to every resource, in addition to the "
        "app.kubernetes.io labels computed by the module.",
        {},
        per_environment=True,
    ),
    optional(
        "annotations",
        "map(string)",
        "Annotations applied to every resource. Leave empty if no controller "
        "of the cluster expects any.",
        {},
    ),
)
