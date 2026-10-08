"""Vocabulary of the Helm component catalogue.

The counterpart of `plugins/ansible/catalog/definition.py`: the Ansible domain
catalogues **roles**, the Helm domain catalogues Kubernetes **resource
families**.

A family states what it produces (kind, apiVersion), on what condition it
applies, which `values.yaml` keys it exposes, and — this is the part that
matters — **what breaks when it is written wrong**. Those traps are not
decorative documentation: `kubeconform -strict` refuses a missing `pathType`,
the API refuses a modified `roleRef`, and a `policyTypes: [Egress]` with no rule
cuts DNS off. Recording them here, once, avoids rediscovering them in every
template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: How forge knows that a family applies to a component.
#:
#: * `kind`  — the component *is* of that type (`kind: statefulset`);
#: * `addon` — the component *carries* that addon (`addons: [ingress]`);
#: * `derive`— forge decides on its own (the connection test targets the first
#:   exposed component).
Selection = Literal["kind", "addon", "derive"]


@dataclass(frozen=True)
class ValueKey:
    """A `values.yaml` key exposed to the user.

    Every generated key must carry a comment saying what it is for and which
    values it accepts: that is a hard rule of the project.
    """

    #: Path of the key under the component block (`ingress.pathType`).
    name: str

    #: Default value, written as-is into the generated YAML.
    default: str

    #: What the key is for, in one sentence.
    description: str

    #: Accepted values, when they are constrained.
    allowed: str = ""


@dataclass(frozen=True)
class ComponentFamily:
    """A family of Kubernetes resources generatable for a component."""

    #: Identifier used in forge.yml and in `domain.component_slots`.
    name: str

    #: Kubernetes kind produced — never invented (hard rule of CLAUDE.md).
    kind: str

    #: apiVersion of the kind, for the version window the project targets.
    api_version: str

    #: One-line summary, displayed by `forge catalog helm`.
    summary: str

    #: How forge knows the family applies.
    selection: Selection

    #: Long description, displayed by `forge catalog helm <family>`.
    details: str = ""

    #: `values.yaml` keys exposed by the family.
    values: tuple[ValueKey, ...] = ()

    #: Families this one depends on to make sense.
    requires: tuple[str, ...] = ()

    #: Traps that make `kubeconform -strict`, `helm lint`, or the actual apply
    #: of the manifest fail. One per entry, phrased as a constraint to respect.
    traps: tuple[str, ...] = field(default_factory=tuple)

    def option_descriptions(self) -> dict[str, str]:
        """Values keys and their description, for `forge catalog`."""
        return {
            key.name: (
                f"{key.description} (default: {key.default}"
                + (f"; values: {key.allowed}" if key.allowed else "")
                + ")"
            )
            for key in self.values
        }
